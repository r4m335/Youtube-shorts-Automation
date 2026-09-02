from enum import Enum

class XSessionState(Enum):
    VALID = "valid"
    EXPIRED = "expired"
    LOGIN_REQUIRED = "login_required"
    CHALLENGE = "challenge"

class XScraperError(Exception):
    pass

class XNetworkError(XScraperError):
    pass

class XTimeoutError(XScraperError):
    pass

class XParseError(XScraperError):
    pass
