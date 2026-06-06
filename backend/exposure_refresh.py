import json

from exposure_engine import FORMULA_TEXT, refresh_exposure_scores


def main() -> None:
    payload = refresh_exposure_scores()
    summary = {
        "refreshed_at": payload["refreshed_at"],
        "formula": FORMULA_TEXT,
        "tickers": sorted(payload["scores"].keys()),
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
