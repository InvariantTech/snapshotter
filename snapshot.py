from argparse import ArgumentParser, ArgumentTypeError
import json
import os
import re
import shutil
import pathlib
import tempfile
from netconan.anonymize_files import anonymize_files
from netconan.ip_anonymization import IpAnonymizer
from netconan import sensitive_item_removal
from bf_aws_snapshot import aws_data_getter
from bf_aws_snapshot import awshelper

DEENCRYPTED = "fakefakefakefake"
ENCRYPTED = "\"$9$/B66ApBIRSevL69ORhcvMwYgoJDmPQF39GD.5z3tp0BIcrvx7V\""

def contains_string(file_path, search_string):
  """Check if the file contains the specified string."""
  try:
    with open(file_path, 'r') as file:
      content = file.read()
      return search_string in content
  except Exception as e:
    print(f"Error reading {file_path}: {e}")
    return False

def copy_git_dir(src_dir, dest_dir):
  for root, _, files in os.walk(src_dir):
      for file in files:
        src_file_path = os.path.join(root, file)
        if contains_string(src_file_path, "JUNOS"):
          # Calculate the relative path and create the corresponding directory in destination
          rel_path = os.path.relpath(root, src_dir)
          dest_dir_path = os.path.join(dest_dir, rel_path)
          if not os.path.exists(dest_dir_path):
            os.makedirs(dest_dir_path)
          with open(src_file_path) as f:
            content = ''.join([line for line in f.readlines() if not line.startswith('#') and not line.startswith('set ')])
            # Filter for secrets and replace them with the same thing
            content = re.sub(r"(?<=pre-shared-key ascii-text )\/\* SECRET-DATA \*\/", ENCRYPTED, content)
          with open(os.path.join(dest_dir_path, file), 'w') as f:
            f.write(content)
          
    
def run_aws_snapshot(regions, role, output_dir):
  skip_data = {
    "ClassicLinkInstances": "No support",
    "DhcpOptions": "No support",
    "Hosts": "No support",
    "InstanceStatuses": "Information available elsewhere",
    "MovingAddressStatuses": "Unnecessary info",
    "PlacementGroups": "No support",
    "Tags": "Interfere with parsing because top-level key is Vpcs",
    "VpcClassicLink": "Interfere with parsing because top-level key is Vpcs",
    "VpcClassicLinkDnsSupport": "Interfere with parsing because top-level key is Vpcs"
  }
  sessions = []
  for account in awshelper.get_aws_accounts([]):
    session = awshelper.get_aws_sessions(account['Id'], role)
    if session:
      name = account['Name']
      sessions.append((name, session))
  for session in sessions:
      print(f"Processing account: {session[0]}")
      awshelper.aws_init(regions, [], skip_data, session[1])
      aws_data_getter.snapshot_configs(output_dir, session[0])

def fix_vpn_connections(path):
  for root, _, files in os.walk(pathlib.Path(path).joinpath('aws_configs')):
    for file in files:
      if file == 'VpnConnections.json':
        with open(os.path.join(root, file)) as of:
          
          content = json.load(of)
          for connection in content['VpnConnections']:
            connection['Options']['TunnelOptions'][0]['PreSharedKey'] = DEENCRYPTED
            connection['Options']['TunnelOptions'][1]['PreSharedKey'] = DEENCRYPTED
        with open(os.path.join(root, file), 'w') as of:
          json.dump(content, of, indent=2)
        pass
  pass

def main():
  parser = ArgumentParser(description="snapshot")
  parser.add_argument('-o', '--output-folder', dest='output_folder', help="output folder.", required=True)
  parser.add_argument('-r', '--role', dest='role', help="Role for snapshotting AWS.", required=True)
  parser.add_argument('--regions', nargs="+", dest='regions', help="Regions to snapshot.", required=True)
  parser.add_argument('-g', '--git-folder', dest='git_folder', help="Git directory containing Oxidized backups.", required=True)
  args = parser.parse_args()

  if not os.path.exists(args.output_folder):
    os.makedirs(args.output_folder)
  with tempfile.TemporaryDirectory() as temp_dir:
    temp_path = pathlib.Path(temp_dir)
    copy_git_dir(args.git_folder, temp_path.joinpath('configs'))
    run_aws_snapshot(args.regions, args.role, temp_dir)
    fix_vpn_connections(temp_path)
    shutil.move(temp_dir, args.output_folder)
    

if __name__ == "__main__":
  main()