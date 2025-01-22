# snapshotter

# Installing for development
python3 -m venv .venv 
source .venv/bin/activate
pip3 install -e requirements.txt


# example run
python snapshot.py -g /Users/rankeny/Downloads/fake_git -o /Users/rankeny/snapshotter/output --regions us-west-2 -r NetworkEngineer