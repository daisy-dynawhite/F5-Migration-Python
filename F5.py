#!/usr/bin/env python3

# Import libraries
from netmiko import ConnectHandler
import getpass, yaml, time, logging, sys

# Function to setup global / YAML variables
def setup_vars():

	# Create global VARS
	global admin
	global adminpword
	global config_data
	
	# Print banner
	print("\n*** F5 Migration Script ***\n\nPlease enter credentials!\n")
	
	# Setup logging
	logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s', datefmt='%d %b %y - %H:%M:%S')
	
	# Capture credentials
	admin = getpass.getpass('Admin Username: ')
	adminpword = getpass.getpass(prompt='\nAdmin Password: ')

	# Load script variables via YAML
	try:
		with open('F5.yaml', 'r') as vars:
			config_data = yaml.safe_load(vars)
			return True

	except Exception as e:
		logging.info(f"Error importing YAML vars: {e}")
		return False
 
# Setup Netmiko constructs
def setup_connections(config_data, admin, adminpword):
	
	# Import devices list of dictionaries
	devicevars = config_data.get('devices',[])[0]
	
	devices = {
		'nc_legfw1': {'host': devicevars['legipfw1'], 'device_type': 'f5_ltm'},	 
		'nc_legfw2': {'host': devicevars['legipfw2'], 'device_type': 'f5_ltm'},
		'nc_newfw1': {'host': devicevars['newipfw1'], 'device_type': 'f5_ltm'},
		'nc_newfw2': {'host': devicevars['newipfw2'], 'device_type': 'f5_ltm'},
		'nc_rtr1': {'host': devicevars['router1'], 'device_type': 'cisco_xe'},
		'nc_rtr2': {'host': devicevars['router2'], 'device_type': 'cisco_xe'},	
	}	
	
	connections = {}
	
	try:
		for name, device_info in devices.items():
			connections[name] = ConnectHandler(
			device_type=device_info['device_type'],
			host=device_info['host'],
			username=admin,
			password=adminpword
			)
			
	except Exception as e:
		logging.info(f"Error connecting to devices: {e}")
		sys.exit(100)

	time.sleep(0.5)
	return connections

# Delete Self-IPs on legacy infra
def delete_sip(connection, cmd_chgpart, cmd_delsip, cmd_chksip, sip_part, sip_name):
	
	try:
		# Send SIP delete commands
		del_cmd = connection.send_command(f"{cmd_chgpart};{cmd_delsip}", expect_string=sip_part)
		
		if "Syntax Error" in del_cmd:
			raise Exception(f"SIP deletion command unsuccesful - {del_cmd}!\n")
			sys.exit(801)
			
		# Introduce pause to allow ConfigSync to operate
		time.sleep(0.3)
		
		# Check if SIP deleted correctly
		check = connection.send_command(f"{cmd_chksip}", expect_string=sip_part)
		if "not found" in check:
			logging.info(f"Self-IP {sip_name} deleted successfully on legacy FW!\n")
		else:
			raise Exception(f"Error deleting SIP - {sip_name}")
			sys.exit(802)
	
	except Exception as e:
		logging.info(f"Error deleting Self-IPs: {e}")
		sys.exit(800)

# Create Self-IPs on new infra
def create_sip(connection, cmd_chgpart, cmd_addsip, cmd_chksip, sip_part, sip_name):
	
	global file
	
	try:
		# Send SIP create commands
		create_cmd = connection.send_command(f"{cmd_chgpart};{cmd_addsip}", expect_string=sip_part)
		
		if "Syntax Error" in create_cmd:
			raise Exception(f"SIP creation command unsuccesful - {create_cmd}!\n")
			sys.exit(901)		 
		
		# Introduce pause to allow ConfigSync to operate
		time.sleep(0.3)
		
		# Check if SIP was created correctly
		check = connection.send_command(f"{cmd_chksip}", expect_string=sip_part)
		if (f"net self {sip_name}") in check:
			logging.info(f"Self-IP {sip_name} created successfully on new FW'!\n")
			# Remove prompt
			pvtchk = check.split('adm.')[0]
			file.write('Self-IP '+ sip_name + ' migrated to new firewall:\n\n')
			file.write(pvtchk)
		else:
			raise Exception(f"Error creating SIP {sip_name}")
			sys.exit(902)

	except Exception as e:
		logging.info(f"Error creating Self-IPs: {e}")
		sys.exit(900)

# Delete pools on legacy infra
def delete_pool(connection, cmd_delpl, cmd_chkpl, pl_name, pl_part):
	
	try:
		# Send pool delete commands
		del_cmd = connection.send_command(f"{cmd_delpl}", expect_string=r'\(/' + pl_part + r'\)')
		
		if "Syntax Error" in del_cmd:
			raise Exception(f"Pool deletion command unsuccesful - {del_cmd}!\n")
			sys.exit(601)
		
		
		# Introduce pause to allow ConfigSync to operate
		time.sleep(0.3)
		
		# Check if pool was deleted correctly
		check = connection.send_command(f"{cmd_chkpl}",	 expect_string=r'\(/' + pl_part + r'\)')
		if "not found" in check:
			logging.info(f"Pool {pl_name} deleted successfully on legacy FW!\n")
		else:
			raise Exception(f"Error deleting pool - {pl_name}")
			sys.exit(602)
	
	except Exception as e:
		logging.info(f"Error deleting pools: {e}")
		sys.exit(600)

# Create virtual-servers on new infra
def create_vsvr(connection, cmd_addvs, cmd_chkvs, vs_name, vs_part):
	
	global file
	
	try:
		# Send virtual-server create commands
		create_cmd = connection.send_command(f"{cmd_addvs}", expect_string=r'\(/' + vs_part + r'\)')
		
		if "Syntax Error" in create_cmd or "references" in create_cmd or "not found" in create_cmd:
			raise Exception(f"Pool creation command unsuccesful - {create_cmd}!\n")
			sys.exit(401)

		# Introduce pause to allow ConfigSync to operate
		time.sleep(0.3)
		
		# Check if virtual-server was created correctly	   
		check = connection.send_command(f"{cmd_chkvs}",	 expect_string=r'\(/' + vs_part + r'\)')
		
		if (f"ltm virtual {vs_name}") in check:
			logging.info(f"Virtual-server {vs_name} created successfully on new FW!\n")
			pvtchk = check.split('adm.')[0]
			file.write('VS '+ vs_name + ' migrated to new firewall:\n\n')
			file.write(pvtchk + '\n\n')
		else:
			raise Exception(f"Error creating vs - {vs_name}")
			sys.exit(402)
	
	except Exception as e:
		logging.info(f"Error creating virtual-server: {e}")
		sys.exit(400)

# Delete virtual-servers on legacy infra
def delete_vsvr(connection, cmd_delvs, cmd_chkvs, vs_name, vs_part):
	
	try:
		# Send virtual-server delete commands
		del_cmd = connection.send_command(f"{cmd_delvs}", expect_string=r'\(/' + vs_part + r'\)')
		
		if "Syntax Error" in del_cmd:
			raise Exception(f"Virtual server deletion command unsuccessful - {del_cmd}!\n")
			sys.exit(301)		 
		
		# Introduce pause to allow ConfigSync to operate
		time.sleep(0.3)
		
		# Check if virtual-server was deleted correctly	   
		check = connection.send_command(f"{cmd_chkvs}",	 expect_string=r'\(/' + vs_part + r'\)')
		if "not found" in check:
			logging.info(f"Virtual-server {vs_name} deleted successfully from legacy FW!\n")
		else:
			raise Exception(f"Error deleting virtual-server: {vs_name}")
			sys.exit(302)
	
	except Exception as e:
		logging.info(f"Error deleting virtual-server: {e}")
		sys.exit(300)

# Function to process F5 Self-IPs
def process_sips(config_data, connections):
   
	# Load in SIPs from YAML and iterate through list of dictionaries
	self_ips = config_data.get('sips',[])
	for self_ip in self_ips:
		sip_name = self_ip['name']
		sip_address = self_ip['address']
		sip_part = self_ip['partition']
		sip_netmask = self_ip['netmask']
		sip_vlan = self_ip['vlan']
		sip_fw = self_ip['fw']
		sip_tg = self_ip['tg']
		
		#Declare function variables
		cmd_chgpart = f"cd /{sip_part}"
		cmd_delsip = f"delete net self {sip_name}"
		cmd_chksip = f"list net self {sip_name}"
		cmd_addsip = f"create net self {sip_name} address {sip_address}/{sip_netmask} vlan {sip_vlan} traffic-group {sip_tg}"
		
		#Evaluate SIP type and process using del/create SIP functions
		try:
			if "legfw" in sip_fw:
				if "legfw1" in sip_fw:
					delete_sip(connections['nc_legfw1'], cmd_chgpart, cmd_delsip, cmd_chksip, sip_part, sip_name)
				elif "legfw2" in sip_fw:
					delete_sip(connections['nc_legfw2'], cmd_chgpart, cmd_delsip, cmd_chksip, sip_part, sip_name)
				else:
					delete_sip(connections['nc_legfw2'], cmd_chgpart, cmd_delsip, cmd_chksip, sip_part, sip_name)
			elif "newfw" in sip_fw:
				if "newfw1" in sip_fw:
					create_sip(connections['nc_newfw1'], cmd_chgpart, cmd_addsip, cmd_chksip, sip_part, sip_name)
				elif "newfw2" in sip_fw:
					create_sip(connections['nc_newfw2'], cmd_chgpart, cmd_addsip, cmd_chksip, sip_part, sip_name)
				else:
					create_sip(connections['nc_newfw2'], cmd_chgpart, cmd_addsip, cmd_chksip, sip_part, sip_name)
			else:
				raise Exception(f"SIP variables not correct in YAML file: {sip_fw}")
				sys.exit(701)
		
		except Exception as e:
			logging.info(f"Error processing Self-IPs: {e}")		
			sys.exit(700)

# Function to process LTM activities
def process_ltm(config_data, connections):

	# Use script flags to determine whether LTM work is required
	flags = config_data.get('flags',[])
	for flag in flags:
		pools = flag['pools']
		vsvr = flag['vsvr']

	# If VLAN has virtual-servers requiring deletion
	if 'ja' in vsvr:
		vsvrdata = config_data.get('vs',[])
		
		try:
			for vs in vsvrdata:
				# Delete VS from legacy infra
				vs_name = vs['vsname']
				vs_delpart = vs['vsdelpart']
				vs_addpart = vs['vsaddpart']
				cmd_delvs = f"cd /{vs_delpart}/;{vs['vsdel']}"
				cmd_chkvs = f"list ltm virtual {vs_name}"
				delete_vsvr(connections['nc_legfw2'], cmd_delvs, cmd_chkvs, vs_name, vs_delpart)
				
				# Add VS to new infra
				cmd_addvs = f"cd /{vs_addpart}/;{vs['vsadd']}"
				create_vsvr(connections['nc_newfw2'], cmd_addvs, cmd_chkvs, vs_name, vs_addpart)
		
		except Exception as e:
			logging.info(f"Error processing virtual-servers: {e}")
			sys.exit(200)
			
	elif 'ja' not in vsvr:
		logging.info("No virtual servers associated with VLAN")
		
	# If VLAN has pools requiring deletion
	if 'ja' in pools:
		pooldata = config_data.get('pools',[])
		
		try:
			# Iterate through pools and delete from legacy FWs
			for pool in pooldata:

				#Del pool
				pl_name = pool['poolname']
				pl_delpart = pool['pooldelpart']
				cmd_delpl = f"cd /{pl_delpart}/;{pool['pooldel']}"
				cmd_chkpl = f"list ltm pool {pl_name}"
				delete_pool(connections['nc_legfw2'], cmd_delpl, cmd_chkpl, pl_name, pl_delpart)
		
		except Exception as e:
			logging.info(f"Error processing pools: {e}")
			sys.exit(500)
			
	elif 'ja' not in pools:
		logging.info("No pools associated with VLAN")

# Function to update front-end routing
def process_rtrs(config_data, connections):
	
	try:
		#Iterate through YAML vars and execute.
		statroutes = config_data.get('routes',[])

		for routes in statroutes:
			ips = routes['ips']
			mask = routes['mask']
			vrf = routes['vrf']
			nh = routes['nh']
			name = routes['name']

		sroute = (f"ip route vrf {vrf} {ips} {mask} {nh} name {name}")
		connections['nc_rtr1'].send_config_set(sroute)
		logging.info(f"Static route for {ips} / {mask} in vrf {vrf} created on DAYZ-RTR-001!\n")
		connections['nc_rtr2'].send_config_set(sroute)
		logging.info(f"Static route for {ips} / {mask} in vrf {vrf} created on DAYZ-RTR-002!\n")

	except Exception as e:
		logging.info(f"Error creating route: {e}")
		sys.exit(1000)		 

# Main process function
def main():

	print("\nScript output: \n")
	
	# Load PVT TXT file
	global file
	file = open('F5-Migration-PVT.txt','w')
	file.write('\n*** F5 PVT Script *** \n\n')
	
	# Connect to devices via function
	logging.info("Device connections:\n")
	connections = setup_connections(config_data, admin, adminpword)
	logging.info("Netmiko connections established\n")
	input("All connections are established, hit enter to continue, CTRL-Z to exit")
	print("\n")
	
	# Start duration timer
	start_time = time.perf_counter()
	
	# Process LTM where required
	process_ltm(config_data, connections)
	
	# Process Self-IPs
	process_sips(config_data, connections)
	
	# Process routing
	process_rtrs(config_data, connections)
	
	#Process script duration
	end_time = time.perf_counter()
	timediff = end_time - start_time
	print(f"Time elapsed: {timediff:.2f} seconds.")
	
	# Close PVT
	file.close()

# Call main function
if __name__ == "__main__":
	if setup_vars():
		main()
		print("\nScript completed\n")
	else:
		print("Main script not started, issue with vars")
