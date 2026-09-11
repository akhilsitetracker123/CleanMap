"""Generate bcrypt password hashes for CleanMap secrets.toml (optional)."""

import getpass
import sys

import streamlit_authenticator as stauth


def main() -> None:
    if len(sys.argv) > 1:
        password = sys.argv[1]
    else:
        password = getpass.getpass("Password to hash: ")
    if not password:
        print("No password entered.")
        sys.exit(1)
    hashed = stauth.Hasher.hash(password)
    print("\nAdd this hash to .streamlit/secrets.toml under the user's password field:\n")
    print(hashed)


if __name__ == "__main__":
    main()
