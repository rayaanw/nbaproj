"""Smoke test: import every core dependency and print its version.

Run after `pip install -r requirements.txt` to confirm the environment is healthy
before running any real pipeline steps.
"""

import importlib
import importlib.metadata

# Maps the importable module name to its PyPI distribution name (only needed
# when they differ) so we can look up the installed version reliably.
DIST_NAME_OVERRIDES = {
    "sklearn": "scikit-learn",
    "dotenv": "python-dotenv",
}

PACKAGES = [
    "nba_api",
    "pandas",
    "numpy",
    "xgboost",
    "sklearn",
    "matplotlib",
    "flask",
    "dotenv",
    "pyarrow",
]


def main() -> None:
    failures = []
    for package_name in PACKAGES:
        try:
            importlib.import_module(package_name)
            dist_name = DIST_NAME_OVERRIDES.get(package_name, package_name)
            try:
                version = importlib.metadata.version(dist_name)
            except importlib.metadata.PackageNotFoundError:
                version = "unknown"
            print(f"OK   {package_name:<12} {version}")
        except ImportError as exc:
            failures.append(package_name)
            print(f"FAIL {package_name:<12} {exc}")

    if failures:
        raise SystemExit(f"Missing packages: {', '.join(failures)}")

    print("\nAll packages imported successfully.")


if __name__ == "__main__":
    main()
