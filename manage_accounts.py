import json
import requests

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
	resolve_url = "https://api-mobi.soundcloud.com/resolve?permalink_url=" + link + "&client_id=iZIs9mchVcX5lhVRyQGGAYlNPVldzAoX&format=json&app_version=1582537945"
	r = requests.get(resolve_url)
	r = r.content
	x = json.loads(r)
	return x["username"]

def add_account(link):
	data['accounts'].append({
	    'account': '{}'.format(link),
	    'name': '{}'.format(get_name_account(link))
	})

txt = ''
while (txt != '0'):
	txt = input("please enter a URL [0] to quit: ")
	if(txt != '0'):
		add_account(txt)

with open('accounts.json', 'w') as outfile:
    json.dump(data, outfile)
    outfile.close()