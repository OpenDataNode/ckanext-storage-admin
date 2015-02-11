About
-------

CKAN extension reporting aggregate and per organisation data usage.

Features:

 - returns stats for every CKAN organisation separately, or for the whole CKAN instance combined
 - reports number of bytes used in FileStore
 - reports number of bytes used in DataStore
 - reports number of triples stored in Virtuoso triplestore

Requirements
-------

In order to access Virtuoso as an SQL database, you need to install ODBC driver manager with Virtuoso driver, and configure a DSN for your Virtuoso instance. Here is an example for Ubuntu based distros, with local Virtuoso instance:

Install iODBC with Virtuoso driver:
```bash
sudo apt-get install libiodbc2 libvirtodbc0
```

Sample ~/.odbc.ini:
```ApacheConf
[ODBC Data Sources]
Virtuoso = Virtuoso ODBC Driver

[Virtuoso]
Driver  = /usr/lib/odbc/virtodbc.so
Address = localhost:1111
```


Installation
-------

Activate ckan virtualenv: 
```bash
. /usr/lib/ckan/default/bin/activate
```

Start the installation from the extension directory:
```bash
cd ckanext-storage-admin
python setup.py install
```

Add extension to ckan config, typically ```/etc/ckan/default/production.ini```:

```ApacheConf
[app:main]
ckan.plugins = ... storage_admin
```

Configuration
-------

Extension reads data from 3 different sources. All of them are configured separately.

**Filesystem**

FileStore path is configured in ckan configuration file as ```ckan.storage_path``` key. You should have this in your config already.
Example:
```ApacheConf
ckan.storage_path = /home/ckan/storage
```

**Database**

Connection strings for the PostgreSQL instance are configured in ckan configuration file. This extension uses the read-only user:
```
ckan.datastore.read_url = postgresql://datastore_default:datastore_default@localhost/datastore_default
```
You should have this already if you've configured the DataStore extension.


The name of the scheme for DataStore is configured separately:
```
edemo.storage.admin.datastore.schema = public
```

**Triplestore**

Virtuoso is used here both as an SPARQL endpoint, and as a SQL database, so both methods need to be configured.

* The SPARQL endpoint URL:
```
edemo.storage.admin.sparql.endpoint = http://localhost:8890/sparql
```

* The ODBC DSN:
```
edemo.storage.admin.virtuoso.dsn = "DSN=Virtuoso;UID=dba;PWD=dba;"
```
Name of the DSN comes from the ODBC configuration file, typically ```~/.odbc.ini```

**TLDR;**

```ApacheConf
[app:main]
ckan.storage_path = /home/ckan/storage
ckan.datastore.read_url = postgresql://datastore_default:datastore_default@localhost/datastore_default

edemo.storage.admin.datastore.schema = public
edemo.storage.admin.sparql.endpoint = http://localhost:8890/sparql
edemo.storage.admin.virtuoso.dsn = "DSN=Virtuoso;UID=dba;PWD=dba;"
```


Usage
-------

There are 2 usage patterns: from CKAN extensions, and through the CKAN API.

**CKAN extension usage:**
```python
import ckan.logic as logic
get_action = logic.get_action

# aggregate stats for whole CKAN instance
aggregate_stats = get_action('used_space')(context, {})
print 'FileStore uses: {0} bytes'.format(aggregate_stats['filesystem'])
print 'DataStore uses: {0} bytes'.format(aggregate_stats['database'])
print 'Triplestore has: {0} triples'.format(aggregate_stats['triplestore'])

# per organisation stats
per_org_stats = get_action('used_space_per_org')(context, {})
for key, value in per_org_stats.iteritems():
  print 'Stats for organisation id {0}:'.format(key)
  print 'FileStore uses: {0} bytes'.format(value['filesystem'])
  print 'DataStore uses: {0} bytes'.format(value['database'])
  print 'Triplestore has: {0} triples'.format(value['triplestore'])
```

**CKAN API usage:**

For easy experimenation, you can use the prepared [Postman](http://www.getpostman.com/) collection: [ckanext-admin-storage.json.postman_collection](ckanext-admin-storage.json.postman_collection)

You can also fire your requests using cURL. The CKAN API used here as an example is reachable at ```http://127.0.0.1:5000/api/3```, you will need to update the examples to fit your deployment.

For aggregate stats:
```bash
curl -X POST -H "Content-Type: application/json" -H "Cache-Control: no-cache" -d '{}' http://127.0.0.1:5000/api/3/action/used_space
```

Sample response:
```json
{
  "success": true,
  "result": {
    "triplestore": 1337,
    "filesystem": 393450,
    "database": 32768
  }
}
```

And for per organisation stats:
```bash
curl -X POST -H "Content-Type: application/json" -H "Cache-Control: no-cache" -d '{}' http://127.0.0.1:5000/api/3/action/used_space_per_org
```

Sample response, containing one organization, with id ```6dc5a13f-6eaa-43a4-ac17-d5de6be8f98a```:
```json
{
  "success": true,
  "result": {
    "6dc5a13f-6eaa-43a4-ac17-d5de6be8f98a": {
      "triplestore": 1337,
      "filesystem": 393450,
      "database": 32768
    }
  }
}
```

License
-------

Licensed under [GNU Affero General Public License, Version 3.0](http://www.gnu.org/licenses/agpl-3.0.html). See [LICENSE](LICENSE).
