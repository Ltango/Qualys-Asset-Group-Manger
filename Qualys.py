#!/usr/bin/python
# -*- coding: utf-8 -*-
 
import requests
import xml.etree.ElementTree as ET
import getpass
import json
import time
import logging
import os
import re
import atexit
import ipaddress
from threading import BoundedSemaphore as BoundedSemaphore, Timer
from argparse import ArgumentParser


#Handle Parsing of arguments
parser = ArgumentParser()
parser.add_argument("-r", "--readfile", help = "Enter text file name for list of IPs that need to be imported e.g.: 'Python Qualys.py -r example.txt'", required = False)
parser.add_argument("-o", "--overwrite", help = "Overwrite Qualys Asset groups if they already exist", required = False)
parser.add_argument("-s", "--savetemp", help = "Do not delete temporary files on close (debugging tool)", required = False)
parser.add_argument("-l", "--limit", help = "change the default value from 200 calls per hour to Qualys", required = False)
args = vars(parser.parse_args())
 
 
#Set up logging
logging.basicConfig(filename='Qualys Tool Log.log',
					filemode = 'a',
					format = '[%(asctime)s] %(levelname)s %(name)s %(message)s',
					datefmt = '%m/%d/%Y %I:%M:%S %p',
					level = logging.DEBUG)

 
 
#This is our Rate Limiting Class - we use it to make sure that we don't send too many requests to Qualys.
class RatedSemaphore(BoundedSemaphore):
	#Limit to 1 request per `period / value` seconds (over long run).
	def __init__(self, value=1, period=1):
		BoundedSemaphore.__init__(self, value)
		t = Timer(period, self._add_token_loop,
				  kwargs=dict(time_delta=float(period) / value))
		t.daemon = True
		t.start()

	def _add_token_loop(self, time_delta):
		#Add token every time_delta seconds.
		while True:
			try:
				BoundedSemaphore.release(self)
			except ValueError: # ignore if already max possible value
				pass
			time.sleep(time_delta) # ignore EINTR

	def release(self):
		pass # do nothing (only time-based release() is allowed)

limit_per_hour = 200
if args["limit"] is not None:
	limit_per_hour = int(args["limit"])

rate_limit = RatedSemaphore(limit_per_hour, 3600)
 
#Qualys session login
def login(s):	
	qualysUsername = input('Enter Qualys Username: ')  
	qualysPassword = getpass.getpass('Enter Qualys Password: ')  
	
	payload = {

			   'action':'login',

			   'username':qualysUsername,

			   'password':qualysPassword

			   }

	r = s.post('https://qualysapi.qualys.com/api/2.0/fo/session/', data=payload)
	# Now that all the hard work was done, lets parse the response.
	xmlreturn = ET.fromstring(r.text)
	for elem in xmlreturn.findall('.//TEXT'):
		print(elem.text) #Prints the "Logged in" message. Not really needed, but reassuring.
		
#Qualys session logout
def logout(s):
	payload = {
			   'action':'logout'
			   }
	r = s.post('https://qualysapi.qualys.com/api/2.0/fo/session/', data=payload)

	# Now that all the hard work was done, lets parse the response.
	xmlreturn = ET.fromstring(r.text)
	for elem in xmlreturn.findall('.//TEXT'):
		print(elem.text)	  #Prints the "Logged out" message. Not really needed, but reassuring.


#Makes an API request to qualys to create an asset group could be augmented to handle non-200 responses
def create_asset_group(s, title, ips):

	payload = {
		'action' : 'add',
		'title' : title,
		'business_impact' : 'High',
		'ips' : ips

	}
	with rate_limit, s.post('https://qualysapi.qualys.com/api/2.0/fo/asset/group/', data=payload) as response:
		print(response.status_code)
		xmlreturn = ET.fromstring(response.text)
		for elem in xmlreturn.findall('.//TEXT'):
			print("TITLE: " + title + " IP:" + ips + " " + elem.text)
			

#This creates a json file in the form:
# {
# "ips": [
# {
#	 "name" : "Name",
#	 "ip_ranges" : "0.0.0.0-0.0.0.0",
#	 "id" : "000000"
# },
# {
#	 "name" : "Name",
#	 "ip_ranges" : "0.0.0.0-0.0.0.0",
#	 "id" : "000000"
# }
# ]
# }
# Based on a list of every asset group contained within Qualys that we will use while comparing values to find which Asset groups to update and which Asset groups to create from scratch
def get_asset_group_list(s):
	print("Attempting to retrieve and convert single range Qualys Asset Groups to json...")
	print("This may take a while...")
	json_string_builder = '{\n"ips": [\n'
	
	payload = {
		'action' : 'list',
		'output_format' : 'xml',
		'truncation_limit' : '0'
	}
	
	with rate_limit, s.post('https://qualysapi.qualys.com/api/2.0/fo/asset/group/?action=list', data=payload) as response:
		xmlreturn = ET.fromstring(response.text)
		asset_group_name = ""
		qu_id = ""
		count = 0
		for child in xmlreturn[0][1]:
			count = 0
			asset_group_name = child[1].text
			qu_id = str(child[0].text)
			try:
				for ip_item in child[2]:
					ip_text = ip_item.text
					count += 1
				if not count > 1:
					json_string_builder += '{\n\t"name" : "' + asset_group_name + '",\n' + '\t"ip_ranges" : "' + ip_text + '",\n' + '\t"id" : "' + qu_id + '"\n},\n'
			except:
				print("No IPs for: " + child[1].text)
			
		json_string_builder = json_string_builder[:-3]
		json_string_builder += "}\n]\n}"
	
		g = open("qualys_single_range_ips.json", "w+")
		g.write(json_string_builder)
		g.close()
		print("Completed")
	
#Called whenever the program crashes, is interrupted, or finishes.  Does file cleanup, logout, and session close
def exit_program(sesh):
	print("logging out of Qualys")
	logout(sesh)
	sesh.close()
	removed = False
	if args["savetemp"] is None:
		print("Attempting to delete temporary files...")
		if os.path.exists("temptxt.txt"):
			os.remove("temptxt.txt")
			removed = True
		if os.path.exists("tempipsjson.json"):
			os.remove("tempipsjson.json")
			removed = True
		if os.path.exists("qualys_single_range_ips.json"):
			os.remove("qualys_single_range_ips.json")
			removed = True			
			
	else:
		print("Temporary files not deleted.")

	if removed is True:
		print("Successfully deleted temporary files.")
	else:
		print("Temporary files not found.")
		
	logging.info("Luke's Qualys application has finished")
	print("Luke's Qualys application has finished")
	
#This cleans up the given text file creating a temporary file with all lines without IPs stripped that will be used to create a temporary json file later
def strip_non_ips_from_text_file(readfile):
	print("Removing lines without IP addresses...")
	string_builder = ""
	f = open(readfile, "r")
	
	for x in f:
		ip = re.findall( r'[0-9]+(?:\.[0-9]+){3}', x)
		
		if str(ip) != '[]':
			string_builder += x
	f.close()
	
	g = open("temptxt.txt", "w+")
	g.write(string_builder)
	g.close()
	print("Completed")

#Converts our temporary temp.txt file to a temporary json file for ease of use later
def convert_text_file_to_json():
	string_builder = ""
	temp = ""
	f = open("temptxt.txt", "r")
	print("Attempting to create tempipsjson.json from temptxt.txt...")
	string_builder += '{\n"ips": [\n'
	for x in f:
		addr = ipaddress.ip_network(x[:x.find("[")-1])
		new_range = ('%s-%s' % (addr[0], addr[-1]))
		temp = '{\n\t"name" : "' + x[x.find("[")+1:x.find("]")] + '",\n\t"ip" : ' + '"' + new_range + '"\n},\n' 
		string_builder += temp
	
	string_builder = string_builder[:-3]
	string_builder += "}\n]\n}"
	f.close()
	
	g = open("tempipsjson.json", "w+")
	g.write(string_builder)
	g.close()
	print("Completed")
	
#Makes a call to qualys to update an asset groups name
def update_asset_group_name(s, id, title):
	overwrite = False
	if args["overwrite"] is not None:
		overwrite = True
		
		payload = {
			'action' : 'edit',
			'id' : id,
			'set_title' : title
		}

		with rate_limit, s.post('https://qualysapi.qualys.com/api/2.0/fo/asset/group/?action=edit', data=payload) as response:
			print(response.status_code)
			xmlreturn = ET.fromstring(response.text)
			for elem in xmlreturn.findall('.//TEXT'):
				print("TITLE: " + title + " IP:" + ips + " " + elem.text)
	

#Major legwork of the operation, we parse through our two json files and compare all IPs and Names to find out what needs to be updated and what needs to be created, then makes calls to those functions
def compare_and_update(s):
	found = False
	exists = False
	old_name = ""
	new_name = ""
	id = ""

	with open("tempipsjson.json", "r") as bluecat_file:
		bc_data = json.load(bluecat_file)
	with open("qualys_single_range_ips.json", "r") as qualys_file:
		qu_data = json.load(qualys_file)
	count = 0
	if args["overwrite"] is not None:
		print("Overwrite enabled, updating names in Qualys...")	
		logging.info("Overwrite set to true, existing Qualys Asset Groups will be updated.")
	else:
		print("Overwrite disabled, no changes will be made in Qualys.")		
		logging.info("Overwrite is set to false, Qualys Asset Groups will NOT be updated.")
	
	for bc_item in bc_data["ips"]:
		found = False
		exists = False
		for qu_item in qu_data["ips"]:
			if bc_item["ip"] == qu_item["ip_ranges"] and not bc_item["name"] == qu_item["name"]:
				found = True
				old_name = qu_item["name"] 
				new_name = bc_item["name"]
				id = qu_item["id"]
			if bc_item["ip"] == qu_item["ip_ranges"]:
				exists = True
		if found is True:
			print("Should attempt update on [" + id + "]: " + old_name + " >>> " + new_name)
			try:
				update_asset_group_name(s, id, new_name)
			except:
				print("Unable to update: " + old_name + " >>> " + new_name)
		if exists is False:
			print("Should create asset group: IP: " + bc_item["ip"] + "  NAME: " + bc_item["name"])
			create_asset_group(s, bc_item["name"], bc_item["ip"])
	print("Completed")

#Cleans up temporary files if they exist, and launches our main functions
def main():
	logging.info("Luke's Qualys application has started")
	print("Luke's Qualys application has started")
	print("Cleaning up directory...")
	if os.path.exists("temptxt.txt"):
		os.remove("temptxt.txt")
	if os.path.exists("tempipsjson.json"):
		os.remove("tempipsjson.json")
		
	s = requests.Session()
	s.headers.update({'X-Requested-With':'Lukes API management tool'})
	login(s)
	atexit.register(exit_program, sesh = s)
	
	if args["readfile"] is not None:
		readfile = str(args["readfile"])
		if os.path.exists(readfile):
			print("File found")
			if not readfile.endswith('.txt'):
				print('file must be text file')
				sys.exit(0)
			print('Text file found - now doing things... beep... boop...')
			strip_non_ips_from_text_file(readfile)
			convert_text_file_to_json()
		else:
			print('this particular file has not been found in this particular directory...  How particular!')
			sys.exit(0)
	else:
		print('No -r argument')
		sys.exit(0)
		
	get_asset_group_list(s)
	compare_and_update(s)
	

#launch main
if __name__ == "__main__":
	main()
	
	
	


