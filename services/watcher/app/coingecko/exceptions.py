class CoinGeckoError(Exception):
    pass


class CoinGeckoUnavailableError(CoinGeckoError):
    pass


class CoinGeckoRateLimitError(CoinGeckoError):
    pass


class CoinGeckoInvalidCoinError(CoinGeckoError):
    pass