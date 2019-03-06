# Qualys-Asset-Group-Manger

This is the beautiful Qualys script complete with:\n
	Logging\n
	Rate limiting\n
	Exit handling\n
	Temporary file cleanup\n
	Error handling\n

How it works:
	Logs into Qualys\n
	Parses through the given text file and creates a new temporary text file with all lines without IP addresses removed and converts CIDR to IP ranges\n
	Creates a temporary JSON file with the IP ranges and Names from the temporary text file we created\n
	Make a call to Qualys to get all asset groups\n
	Create a temporary JSON file with all qualys asset groups that only have a single IP range recording IP range, Name, and asset group ID\n
	Compares the two JSON files to find any differences in names for a matching IP range\n
	Update those names in Qualys if the -o argument is existent\n
	Create the asset groups in Qualys if the IP range is in the given text file but not yet in Qualys\n
	Deletes all temporary files unless the -s argument is existent\n


HOW TO USE\n

1. Copy list of ips/names from blue cat

This script will accept lines in the form:\n
0.0.0.0/24 [Server Name]\n
0.0.0.0/24 [Server Name]\n
0.0.0.0/24 [Server Name]\n
...

Any lines without an ip address will be ignored\n
IP must be before the server name and the server name must be in brackets\n

2. Save the copied list into a text file (Example data.txt) in a directory with the python script Qualys.py

3. Run the script:

	a. Run the script but do not make changes:
		'python Qualys.py -r data.txt' (replacing data.txt with whatever you named your text file)
	b. Run the script and make changes in Qualys
		'python Qualys.py -r data.txt -o true'
	c. Run the script and save temporary files:
		'python Qualys.py -r data.txt -s true'
	d. Run the script and change the default value of calls per hour (Note hard limit currently at 300 and default for this program is 200):
		'python Qualys.py -r data.txt -l ###' (replacing ### with however many calls you want to place per minute)

4. Login using your Qualys credentials and watch the magic work
