import json

from index_loader import OfficialNiftyIndexUniverse


def main() -> None:
    loader = OfficialNiftyIndexUniverse()
    _, metadata = loader.load_for_sectors(loader.available_sectors(), force_refresh=True)
    print(json.dumps({"refreshed": metadata}, indent=2))


if __name__ == "__main__":
    main()
