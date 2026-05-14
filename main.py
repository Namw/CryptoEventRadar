from crypto_market_intel.cli import main as cli_main
from crypto_market_intel.config import load_env


if __name__ == "__main__":
    load_env()
    cli_main()
