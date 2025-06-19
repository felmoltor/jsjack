# Class to print colored text in the terminal

class Colored:
    @staticmethod
    def red(text: str) -> str:
        return f"\033[91m{text}\033[0m"

    @staticmethod
    def green(text: str) -> str:
        return f"\033[92m{text}\033[0m"

    @staticmethod
    def yellow(text: str) -> str:
        return f"\033[93m{text}\033[0m"

    @staticmethod
    def blue(text: str) -> str:
        return f"\033[94m{text}\033[0m"

    @staticmethod
    def magenta(text: str) -> str:
        return f"\033[95m{text}\033[0m"

    @staticmethod
    def cyan(text: str) -> str:
        return f"\033[96m{text}\033[0m"