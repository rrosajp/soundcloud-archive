import sys
import json
import requests

clientId = "iZIs9mchVcX5lhVRyQGGAYlNPVldzAoX"
appVersion = "1582537945"

if len(sys.argv) < 2 or len(sys.argv) > 2:
	print("Usage: python3 {} <0|1>".format(sys.argv[0]))
	print("0 = Enter accounts manually")
	print("1 = Add all accounts followed by a certain user")
	exit()

data = {}
try:	
	with open('accounts.json') as json_file:
		data = json.load(json_file)
		print("Number of accounts: {}".format(len(data['accounts'])))
		json_file.close()
except:
	data = {}
	data['accounts'] = []

def get_name_account(link):
	r = requests.get("https://api-mobi.soundcloud.com/resolve?permalink_url={}&client_id={}&format=json&app_version={}".format(link, clientId, appVersion))
	r = r.content
	x = json.loads(r)
	return x["username"]

def get_user_id(link):
	r = requests.get("https://api-mobi.soundcloud.com/resolve?permalink_url={}&client_id={}&format=json&app_version={}".format(link, clientId, appVersion))
	r = r.content
	x = json.loads(r)
	return x["id"]	


def add_account(link):
	data['accounts'].append({
	    'account': '{}'.format(link),
	    'name': '{}'.format(get_name_account(link))
	})

def get_followed_accounts(id):
	return get_followed_accounts_rec("https://api-v2.soundcloud.com/users/{}/followings?client_id={}&limit=300&offset=0&linked_partitioning=1&app_version={}&app_locale=de".format(id, clientId, appVersion))

def get_followed_accounts_rec(resolve_url):
	r = requests.get(resolve_url)
	r = r.content
	x = json.loads(r)
	accounts = []
	try:
		for i in x["collection"]:
			try:
				accounts.append(i["permalink_url"])
			except:
				pass
	except:
		pass
	try:
		if x["collection"]["next_href"] is not None:
			return accounts + get_followed_accounts_rec(x["collection"]["next_href"])
	except:
		if x["next_href"] is not None:
			return accounts + get_followed_accounts_rec(x["next_href"] + "&client_id={}&linked_partitioning=1&app_version={}&app_locale=de".format(clientId, appVersion))
	return accounts

if len(sys.argv) == 2:
	if sys.argv[1] == "0":
		txt = ''
		while (txt != '0'):
			txt = input("please enter a URL [0] to quit: ")
			if(txt != '0'):
				add_account(txt)

	elif sys.argv[1] == "1":
		exisiting_account_urls = []
		for a in data['accounts']:
			exisiting_account_urls.append(a['account'])
		profile_link = input("Please enter an account URL: ")
		accounts = get_followed_accounts(get_user_id(profile_link))
		for index, a in enumerate(accounts):
			print("\033[K", "Account: [{}/{}]".format(index + 1, len(accounts)), "\r", end='')
			sys.stdout.flush()
			if a not in exisiting_account_urls:
				add_account(a)
		print("")
	else:
		print("You need to enter either 1 or 0...")
		exit()

with open('accounts.json', 'w') as outfile:
    json.dump(data, outfile)
    outfile.close()