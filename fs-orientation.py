import argparse
import os

def list_files(path, orientation):
    try:
        files = [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]
    except FileNotFoundError:
        print(f"Error: Directory '{path}' not found.")
        return
    except PermissionError:
        print(f"Error: Permission denied for '{path}'.")
        return

    if orientation == 'v':
        for f in files:
            print(f)
    else:
        print('  '.join(files))

def main():
    parser = argparse.ArgumentParser(description="List files in a directory with orientation.")
    parser.add_argument("path", help="Path to the directory")
    parser.add_argument("-o", "--orientation", choices=['h', 'v'], default='h',
                        help="Orientation: h for horizontal, v for vertical (default: h)")
    args = parser.parse_args()

    list_files(args.path, args.orientation)

if __name__ == "__main__":
    main()
