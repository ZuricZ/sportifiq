import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--epochs", type=int, default=24)
args = parser.parse_args()
print(args.epochs)
