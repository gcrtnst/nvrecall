import datetime
import http.cookiejar
import unittest

import httpx
import respx

import nvrecall.niconico


class TestDefaultUserAgent(unittest.TestCase):
    def test(self) -> None:
        semver = r"(?:(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)(?:-(?:(?:0|[1-9][0-9]*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9][0-9]*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?(?:\+(?:[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?)"
        self.assertRegex(
            nvrecall.niconico._default_user_agent,
            r"\Anvrecall/" + semver + r" python-httpx/" + semver + r"\z",
        )


class TestNiconicoInit(unittest.TestCase):
    def test(self) -> None:
        cookies = http.cookiejar.CookieJar()

        with nvrecall.niconico.Niconico(
            mail_tel="mail@example.com",
            password="password",
            cookies=cookies,
            user_agent="test_ua",
            timeout=52149,
        ) as n:
            self.assertEqual(n.mail_tel, "mail@example.com")
            self.assertEqual(n.password, "password")
            self.assertIs(n.cookies, cookies)
            self.assertEqual(n.user_agent, "test_ua")
            self.assertEqual(n.timeout, httpx.Timeout(52149))

    def test_default(self) -> None:
        with nvrecall.niconico.Niconico() as n:
            self.assertIsNone(n.mail_tel)
            self.assertIsNone(n.password)
            self.assertIsNone(next(iter(n.cookies), None))
            self.assertEqual(n.user_agent, nvrecall.niconico._default_user_agent)
            self.assertEqual(n.timeout, nvrecall.niconico._default_timeout)

    def test_empty_ua(self) -> None:
        with nvrecall.niconico.Niconico(user_agent=None) as n:
            self.assertIsNone(n.user_agent)


class TestNiconicoClose(unittest.TestCase):
    def test(self) -> None:
        n = nvrecall.niconico.Niconico()
        self.assertFalse(n._httpx.is_closed)
        n.close()
        self.assertTrue(n._httpx.is_closed)


class TestNiconicoContextManagement(unittest.TestCase):
    def test(self) -> None:
        with nvrecall.niconico.Niconico() as n:
            self.assertFalse(n._httpx.is_closed)
        self.assertTrue(n._httpx.is_closed)


class TestNiconicoLogin(unittest.TestCase):
    def test(self) -> None:
        now = datetime.datetime.now().astimezone()
        n = nvrecall.niconico.Niconico(mail_tel="mail@example.com", password="password")

        with respx.mock(assert_all_mocked=True, assert_all_called=True) as respx_mock:
            respx_mock.route(
                method="POST",
                url="https://account.nicovideo.jp/login/redirector",
                data={"mail_tel": "mail@example.com", "password": "password"},
            ).respond(
                status_code=302,
                cookies=[
                    respx.SetCookie(
                        "user_session",
                        "deleted",
                        path="/",
                        expires=datetime.datetime(
                            1970, 1, 1, 0, 0, 0, 0, datetime.timezone.utc
                        ),
                        max_age=-1073741824,
                    ),
                    respx.SetCookie(
                        "user_session",
                        "deleted",
                        path="/",
                        domain=".nicovideo.jp",
                        expires=datetime.datetime(
                            1970, 1, 1, 0, 0, 0, 0, datetime.timezone.utc
                        ),
                        max_age=-1073741824,
                    ),
                    respx.SetCookie(
                        "user_session",
                        "user_session_00000000_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                        path="/",
                        domain=".nicovideo.jp",
                        expires=now + datetime.timedelta(minutes=5),
                        max_age=300,
                        http_only=True,
                        secure=True,
                    ),
                ],
            )

            n.login()

    def test_exc_missing_mail_tel(self) -> None:
        n = nvrecall.niconico.Niconico(password="password")
        with respx.mock(assert_all_mocked=True):
            with self.assertRaises(nvrecall.niconico.NiconicoMissingCredentialsError):
                n.login()

    def test_exc_missing_password(self) -> None:
        n = nvrecall.niconico.Niconico(mail_tel="mail@example.com")
        with respx.mock(assert_all_mocked=True):
            with self.assertRaises(nvrecall.niconico.NiconicoMissingCredentialsError):
                n.login()

    def test_exc_invalid_creds(self) -> None:
        n = nvrecall.niconico.Niconico(mail_tel="mail@example.com", password="password")

        with respx.mock(assert_all_mocked=True, assert_all_called=True) as respx_mock:
            respx_mock.route(
                method="POST",
                url="https://account.nicovideo.jp/login/redirector",
                data={"mail_tel": "mail@example.com", "password": "password"},
            ).respond(
                status_code=302,
                headers={
                    "Location": "https://account.nicovideo.jp/login?message=cant_login"
                },
            )

            with self.assertRaises(
                nvrecall.niconico.NiconicoInvalidCredentialsError
            ) as cm:
                n.login()
            self.assertEqual(cm.exception.mail_tel, "mail@example.com")

    def test_exc_unexpected_missing_cookies(self) -> None:
        n = nvrecall.niconico.Niconico(mail_tel="mail@example.com", password="password")

        with respx.mock(assert_all_mocked=True, assert_all_called=True) as respx_mock:
            respx_mock.route(
                method="POST",
                url="https://account.nicovideo.jp/login/redirector",
                data={"mail_tel": "mail@example.com", "password": "password"},
            ).respond(status_code=302)

            with self.assertRaises(nvrecall.niconico.NiconicoLoginError) as cm:
                n.login()
            self.assertIs(type(cm.exception), nvrecall.niconico.NiconicoLoginError)

    def test_exc_unexpected_missing_user_session(self) -> None:
        now = datetime.datetime.now().astimezone()
        n = nvrecall.niconico.Niconico(mail_tel="mail@example.com", password="password")

        with respx.mock(assert_all_mocked=True, assert_all_called=True) as respx_mock:
            respx_mock.route(
                method="POST",
                url="https://account.nicovideo.jp/login/redirector",
                data={"mail_tel": "mail@example.com", "password": "password"},
            ).respond(
                status_code=302,
                cookies=[
                    respx.SetCookie(
                        "user_session_secure",
                        "user_session_00000000_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                        path="/",
                        domain=".nicovideo.jp",
                        expires=now + datetime.timedelta(minutes=5),
                        max_age=300,
                        http_only=True,
                        secure=True,
                    ),
                    respx.SetCookie(
                        "user_session",
                        "user_session_00000000_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                        path="/",
                        domain="live.nicovideo.jp",
                        expires=now + datetime.timedelta(minutes=5),
                        max_age=300,
                        http_only=True,
                        secure=True,
                    ),
                    respx.SetCookie(
                        "user_session",
                        "deleted",
                        path="/",
                        expires=datetime.datetime(
                            1970, 1, 1, 0, 0, 0, 0, datetime.timezone.utc
                        ),
                        max_age=-1073741824,
                    ),
                    respx.SetCookie(
                        "user_session",
                        "deleted",
                        path="/",
                        domain=".nicovideo.jp",
                        expires=datetime.datetime(
                            1970, 1, 1, 0, 0, 0, 0, datetime.timezone.utc
                        ),
                        max_age=-1073741824,
                    ),
                ],
            )

            with self.assertRaises(nvrecall.niconico.NiconicoLoginError) as cm:
                n.login()
            self.assertIs(type(cm.exception), nvrecall.niconico.NiconicoLoginError)

    def test_exc_unexpected_location(self) -> None:
        for location in [
            "http://account.nicovideo.jp/login?message=cant_login",
            "https://admin:password@account.nicovideo.jp/login?message=cant_login",
            "https://www.nicovideo.jp/login?message=cant_login",
            "https://account.nicovideo.jp/?message=cant_login",
            "https://account.nicovideo.jp/login",
        ]:
            with self.subTest(location=location):
                n = nvrecall.niconico.Niconico(
                    mail_tel="mail@example.com", password="password"
                )

                with respx.mock(
                    assert_all_mocked=True, assert_all_called=True
                ) as respx_mock:
                    respx_mock.route(
                        method="POST",
                        url="https://account.nicovideo.jp/login/redirector",
                        data={"mail_tel": "mail@example.com", "password": "password"},
                    ).respond(status_code=302, headers={"Location": location})

                    with self.assertRaises(nvrecall.niconico.NiconicoLoginError) as cm:
                        n.login()
                    self.assertIs(
                        type(cm.exception), nvrecall.niconico.NiconicoLoginError
                    )


class TestNiconicoAutoLogin(unittest.TestCase):
    def test(self) -> None:
        now = datetime.datetime.now().astimezone()
        n = nvrecall.niconico.Niconico(mail_tel="mail@example.com", password="password")

        with respx.mock(assert_all_mocked=True, assert_all_called=True) as respx_mock:
            respx_mock.route(
                method="POST",
                url="https://account.nicovideo.jp/login/redirector",
                data={"mail_tel": "mail@example.com", "password": "password"},
            ).respond(
                status_code=302,
                cookies=[
                    respx.SetCookie(
                        "dummy1",
                        "value1",
                        path="/",
                        domain=".nicovideo.jp",
                        expires=now + datetime.timedelta(minutes=5),
                        max_age=300,
                        http_only=True,
                        secure=True,
                    ),
                    respx.SetCookie(
                        "user_session",
                        "user_session_00000000_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                        path="/",
                        domain=".nicovideo.jp",
                        expires=now + datetime.timedelta(minutes=5),
                        max_age=300,
                        http_only=True,
                        secure=True,
                    ),
                    respx.SetCookie(
                        "dummy2",
                        "value2",
                        path="/",
                        domain=".nicovideo.jp",
                        expires=now + datetime.timedelta(minutes=5),
                        max_age=300,
                        http_only=True,
                        secure=True,
                    ),
                ],
            )
            n.login()

        in_impl_args = "impl_args_1", "impl_args_2"
        in_impl_kwargs = {"impl_kwargs_1": 1, "impl_kwargs_2": 2}
        in_impl_ret = "impl_ret"
        got_impl_args: tuple[object, ...] | None = None
        got_impl_kwargs: dict[str, object] | None = None
        got_impl_call = 0

        def impl(
            self: nvrecall.niconico.Niconico, *args: object, **kwargs: object
        ) -> object:
            nonlocal got_impl_args, got_impl_kwargs, got_impl_call
            got_impl_args = args
            got_impl_kwargs = kwargs
            got_impl_call += 1

            return in_impl_ret

        with respx.mock(assert_all_mocked=True):
            got_impl_ret = n._autologin(impl)(n, *in_impl_args, **in_impl_kwargs)

        self.assertEqual(got_impl_args, in_impl_args)
        self.assertEqual(got_impl_kwargs, in_impl_kwargs)
        self.assertEqual(got_impl_ret, in_impl_ret)
        self.assertEqual(got_impl_call, 1)

    def test_login_first(self) -> None:
        now = datetime.datetime.now().astimezone()
        n = nvrecall.niconico.Niconico(mail_tel="mail@example.com", password="password")

        login_count = 0

        in_impl_args = "impl_args_1", "impl_args_2"
        in_impl_kwargs = {"impl_kwargs_1": 1, "impl_kwargs_2": 2}
        in_impl_ret = "impl_ret"
        got_impl_args: tuple[object, ...] | None = None
        got_impl_kwargs: dict[str, object] | None = None
        got_impl_call = 0

        def impl(
            self: nvrecall.niconico.Niconico, *args: object, **kwargs: object
        ) -> object:
            nonlocal got_impl_args, got_impl_kwargs, got_impl_call
            got_impl_args = args
            got_impl_kwargs = kwargs
            got_impl_call += 1

            if login_count <= 0:
                raise nvrecall.niconico.NiconicoUnauthorizedError

            return in_impl_ret

        def login(_: httpx.Request) -> httpx.Response:
            nonlocal login_count
            login_count += 1

            return httpx.Response(
                302,
                headers=[
                    respx.SetCookie(
                        "user_session",
                        "user_session_00000000_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                        path="/",
                        domain=".nicovideo.jp",
                        expires=now + datetime.timedelta(minutes=5),
                        max_age=300,
                        http_only=True,
                        secure=True,
                    )
                ],
            )

        with respx.mock(assert_all_mocked=True, assert_all_called=True) as respx_mock:
            respx_mock.route(
                method="POST",
                url="https://account.nicovideo.jp/login/redirector",
                data={"mail_tel": "mail@example.com", "password": "password"},
            ).mock(side_effect=login)

            got_impl_ret = n._autologin(impl)(n, *in_impl_args, **in_impl_kwargs)

        self.assertEqual(got_impl_args, in_impl_args)
        self.assertEqual(got_impl_kwargs, in_impl_kwargs)
        self.assertEqual(got_impl_ret, in_impl_ret)
        self.assertEqual(got_impl_call, 1)
        self.assertEqual(login_count, 1)

    def test_login_again(self) -> None:
        now = datetime.datetime.now().astimezone()
        n = nvrecall.niconico.Niconico(mail_tel="mail@example.com", password="password")

        with respx.mock(assert_all_mocked=True, assert_all_called=True) as respx_mock:
            respx_mock.route(
                method="POST",
                url="https://account.nicovideo.jp/login/redirector",
                data={"mail_tel": "mail@example.com", "password": "password"},
            ).respond(
                status_code=302,
                cookies=[
                    respx.SetCookie(
                        "user_session",
                        "user_session_00000000_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                        path="/",
                        domain=".nicovideo.jp",
                        expires=now + datetime.timedelta(minutes=5),
                        max_age=300,
                        http_only=True,
                        secure=True,
                    )
                ],
            )
            n.login()

        login_count = 0

        in_impl_args = "impl_args_1", "impl_args_2"
        in_impl_kwargs = {"impl_kwargs_1": 1, "impl_kwargs_2": 2}
        in_impl_ret = "impl_ret"
        got_impl_args: tuple[object, ...] | None = None
        got_impl_kwargs: dict[str, object] | None = None
        got_impl_call = 0

        def impl(
            self: nvrecall.niconico.Niconico, *args: object, **kwargs: object
        ) -> object:
            nonlocal got_impl_args, got_impl_kwargs, got_impl_call
            got_impl_args = args
            got_impl_kwargs = kwargs
            got_impl_call += 1

            if login_count <= 0:
                raise nvrecall.niconico.NiconicoUnauthorizedError

            return in_impl_ret

        def login(_: httpx.Request) -> httpx.Response:
            nonlocal login_count
            login_count += 1

            return httpx.Response(
                302,
                headers=[
                    respx.SetCookie(
                        "user_session",
                        "user_session_00000000_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                        path="/",
                        domain=".nicovideo.jp",
                        expires=now + datetime.timedelta(minutes=5),
                        max_age=300,
                        http_only=True,
                        secure=True,
                    )
                ],
            )

        with respx.mock(assert_all_mocked=True, assert_all_called=True) as respx_mock:
            respx_mock.route(
                method="POST",
                url="https://account.nicovideo.jp/login/redirector",
                data={"mail_tel": "mail@example.com", "password": "password"},
            ).mock(side_effect=login)

            got_impl_ret = n._autologin(impl)(n, *in_impl_args, **in_impl_kwargs)

        self.assertEqual(got_impl_args, in_impl_args)
        self.assertEqual(got_impl_kwargs, in_impl_kwargs)
        self.assertEqual(got_impl_ret, in_impl_ret)
        self.assertEqual(got_impl_call, 2)
        self.assertEqual(login_count, 1)

    def test_cookie(self) -> None:
        now = datetime.datetime.now().astimezone()
        n = nvrecall.niconico.Niconico(mail_tel="mail@example.com", password="password")

        with respx.mock(assert_all_mocked=True, assert_all_called=True) as respx_mock:
            respx_mock.route(
                method="POST",
                url="https://account.nicovideo.jp/login/redirector",
                data={"mail_tel": "mail@example.com", "password": "password"},
            ).respond(
                status_code=302,
                cookies=[
                    respx.SetCookie(
                        "user_session_secure",
                        "user_session_00000000_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                        path="/",
                        domain=".nicovideo.jp",
                        expires=now + datetime.timedelta(minutes=5),
                        max_age=300,
                        http_only=True,
                        secure=True,
                    ),
                    respx.SetCookie(
                        "user_session",
                        "user_session_00000000_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                        path="/",
                        domain="live.nicovideo.jp",
                        expires=now + datetime.timedelta(minutes=5),
                        max_age=300,
                        http_only=True,
                        secure=True,
                    ),
                ],
            )

            with self.assertRaises(nvrecall.niconico.NiconicoLoginError):
                n.login()

            # Test that an autologin is attempted when a cookie other than
            # "user_session" exists in the jar. The occurrence of NiconicoLoginError
            # indicates that a login attempt was made.
            with self.assertRaises(nvrecall.niconico.NiconicoLoginError):
                n._autologin(lambda self: None)(n)

    def test_exc_unauthorized(self) -> None:
        now = datetime.datetime.now().astimezone()
        n = nvrecall.niconico.Niconico(mail_tel="mail@example.com", password="password")

        login_count = 0
        impl_count = 0

        def impl(self: nvrecall.niconico.Niconico) -> None:
            nonlocal impl_count
            impl_count += 1

            raise nvrecall.niconico.NiconicoUnauthorizedError

        def login(_: httpx.Request) -> httpx.Response:
            nonlocal login_count
            login_count += 1

            return httpx.Response(
                302,
                headers=[
                    respx.SetCookie(
                        "user_session",
                        "user_session_00000000_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                        path="/",
                        domain=".nicovideo.jp",
                        expires=now + datetime.timedelta(minutes=5),
                        max_age=300,
                        http_only=True,
                        secure=True,
                    )
                ],
            )

        with respx.mock(assert_all_mocked=True, assert_all_called=True) as respx_mock:
            respx_mock.route(
                method="POST",
                url="https://account.nicovideo.jp/login/redirector",
                data={"mail_tel": "mail@example.com", "password": "password"},
            ).mock(side_effect=login)

            with self.assertRaises(nvrecall.niconico.NiconicoUnauthorizedError):
                n._autologin(impl)(n)

        self.assertEqual(login_count, 1)
        self.assertEqual(impl_count, 1)


class TestNiconicoInvalidCredentialsErrorInit(unittest.TestCase):
    def test(self) -> None:
        mail_tel = "mail@example.com"
        extra_args = (1, 2.0, "3")

        exc = nvrecall.niconico.NiconicoInvalidCredentialsError(mail_tel, *extra_args)
        self.assertEqual(exc.mail_tel, "mail@example.com")
        self.assertEqual(exc.args, ("mail@example.com", 1, 2.0, "3"))
