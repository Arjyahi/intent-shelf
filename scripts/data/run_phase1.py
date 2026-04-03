from create_time_split import main as split_main
from preprocess_hm_data import main as preprocess_main
from validate_raw_data import main as validate_main


def main() -> int:
    for step_name, step_main in [
        ("validate", validate_main),
        ("preprocess", preprocess_main),
        ("split", split_main),
    ]:
        exit_code = step_main()
        if exit_code != 0:
            print(f"Phase 1 pipeline stopped during: {step_name}")
            return exit_code

    print("IntentShelf Phase 1 pipeline complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
