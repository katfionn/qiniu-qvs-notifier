"""Main entry point for qvs_notifier command-line tools"""
import sys

def main():
    """Main CLI entry point"""
    if len(sys.argv) < 2:
        print("Usage: python -m qvs_notifier <command>")
        print("\nAvailable commands:")
        print("  tui        - Launch TUI management interface (v2)")
        print("  admin      - Manage admin account")
        print("  installer  - Run first-time installation wizard")
        print("  migrate    - Migrate data from v1 to v2")
        return

    command = sys.argv[1]

    if command == "tui":
        from qvs_notifier.tui_v2 import main as tui_main
        sys.argv = sys.argv[1:]  # Remove command from argv
        tui_main()
    elif command == "admin":
        from qvs_notifier.admin import main as admin_main
        sys.argv = sys.argv[1:]  # Remove command from argv
        admin_main()
    elif command == "installer":
        from qvs_notifier.installer import run_installer
        run_installer()
    elif command == "migrate":
        from scripts.migrate_v1_to_v2 import migrate_v1_to_v2
        migrate_v1_to_v2()
    else:
        print(f"Unknown command: {command}")
        print("\nAvailable commands:")
        print("  tui        - Launch TUI management interface (v2)")
        print("  admin      - Manage admin account")
        print("  installer  - Run first-time installation wizard")
        print("  migrate    - Migrate data from v1 to v2")

if __name__ == "__main__":
    main()
