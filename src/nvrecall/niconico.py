import datetime
import functools
import http.cookiejar
import types
import typing

import httpx

from . import __version__

_default_user_agent: typing.Final[str] = (
    f"nvrecall/{__version__} python-httpx/{httpx.__version__}"
)
_default_timeout: typing.Final[httpx.Timeout] = httpx.Timeout(60)


class Niconico:
    def __init__(
        self,
        *,
        mail_tel: str | None = None,
        password: str | None = None,
        cookies: http.cookiejar.CookieJar | None = None,
        user_agent: str | None = _default_user_agent,
        timeout: float
        | tuple[float, float, float, float]
        | httpx.Timeout
        | None = _default_timeout,
    ) -> None:
        super().__init__()

        client = httpx.Client(
            cookies=cookies,
            http1=True,
            http2=True,
            timeout=timeout,
            default_encoding="utf-8",
        )

        if user_agent is not None:
            client.headers["User-Agent"] = user_agent
        else:
            client.headers.pop("User-Agent", None)

        self._mail_tel: typing.Final[str | None] = mail_tel
        self._password: typing.Final[str | None] = password
        self._httpx: httpx.Client = client

    @property
    def mail_tel(self) -> str | None:
        return self._mail_tel

    @property
    def password(self) -> str | None:
        return self._password

    @property
    def cookies(self) -> http.cookiejar.CookieJar:
        return self._httpx.cookies.jar

    @property
    def user_agent(self) -> str | None:
        return self._httpx.headers.get("User-Agent")

    @property
    def timeout(self) -> httpx.Timeout:
        return self._httpx.timeout

    def close(self) -> None:
        self._httpx.close()

    def __enter__(self) -> typing.Self:
        self._httpx = self._httpx.__enter__()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: types.TracebackType | None,
    ) -> object:
        return self._httpx.__exit__(exc_type, exc_value, traceback)

    @staticmethod
    def _is_user_session(
        cookie: http.cookiejar.Cookie, *, now: datetime.datetime | None = None
    ) -> bool:
        now_epoch = None
        if now is not None:
            now_epoch = int(now.timestamp())

        return (
            cookie.name == "user_session"
            and cookie.domain == ".nicovideo.jp"
            and not cookie.is_expired(now=now_epoch)
        )

    def _get_user_session(
        self, *, now: datetime.datetime | None = None
    ) -> http.cookiejar.Cookie | None:
        if now is None:
            now = datetime.datetime.now().astimezone()

        for cookie in self._httpx.cookies.jar:
            if self._is_user_session(cookie, now=now):
                return cookie
        return None

    def login(self) -> None:
        mail_tel = self._mail_tel
        password = self._password
        if mail_tel is None or password is None:
            raise NiconicoMissingCredentialsError

        resp = self._httpx.request(
            "POST",
            "https://account.nicovideo.jp/login/redirector",
            data={"mail_tel": mail_tel, "password": password},
            follow_redirects=False,
        )

        # Use a single timestamp to ensure consistent expiration checks across
        # multiple cookies. External HTTP requests rely on independent system time.
        now = datetime.datetime.now().astimezone()

        for cookie in resp.cookies.jar:
            if self._is_user_session(cookie, now=now):
                return

        if (
            resp.next_request is not None
            and resp.next_request.url.scheme == "https"
            and resp.next_request.url.userinfo == b""
            and resp.next_request.url.netloc == b"account.nicovideo.jp"
            and resp.next_request.url.path == "/login"
            and resp.next_request.url.params.get("message") == "cant_login"
        ):
            raise NiconicoInvalidCredentialsError(mail_tel)
        raise NiconicoLoginError

    @staticmethod
    def _auto_login[S: Niconico, **P, T](
        func: typing.Callable[typing.Concatenate[S, P], T],
    ) -> typing.Callable[typing.Concatenate[S, P], T]:
        @functools.wraps(func)
        def wrapper(self: S, *args: P.args, **kwargs: P.kwargs) -> T:
            login_attempted = False

            if self._get_user_session() is None:
                self.login()
                login_attempted = True

            try:
                return func(self, *args, **kwargs)
            except NiconicoUnauthorizedError:
                if login_attempted:
                    raise

            self.login()
            return func(self, *args, **kwargs)

        return wrapper


class NiconicoLoginError(Exception):
    pass


class NiconicoMissingCredentialsError(NiconicoLoginError):
    pass


class NiconicoInvalidCredentialsError(NiconicoLoginError):
    def __init__(self, mail_tel: str, *args: object) -> None:
        super().__init__(mail_tel, *args)
        self.mail_tel: typing.Final[str] = mail_tel


class NiconicoUnauthorizedError(Exception):
    pass
