import os
import pylons
import sqlalchemy
import ckan.logic as logic
import ckan.plugins as plugins
import ckan.lib.uploader as uploader
import ckanext.datastore.db as db
import logging
import pypyodbc as pyodbc

from ckan.lib.base import h
from SPARQLWrapper import SPARQLWrapper, JSON

log = logging.getLogger('ckanext')
get_action = logic.get_action

# always use _get_empty() to create a copy
EMPTY = {'filesystem': 0L, 'database': 0L, 'triplestore': 0L}

# these constants should be in CKAN config file
CKAN_DATASTORE_SCHEMA = 'public'
SPARQL_ENDPOINT = "http://localhost:8890/sparql"
VIRTUOSO_DSN = "DSN=Virtuoso;UID=dba;PWD=dba;"


def used_space(context, data_dict=None):
    """
    Returns stats for all 3 components aggregated for all organizations.
    Specifically:
        - filesystem: number of bytes used
        - database: number of bytes used
        - triplestore: number of triplets stored

    Structure of reply:
    {
        'filesystem': <long>,
        'database': <long>,
        'triplestore': <long>
    }

    :param context: standard CKAN action API context instance
    :param data_dict: additional parameters (not used)
    :return: JSON reply
    """
    reply = _get_empty()
    for org_id, sizes in used_space_per_org(context, data_dict).iteritems():
        reply['filesystem'] += long(sizes['filesystem'])
        reply['database'] += long(sizes['database'])

    reply['triplestore'] = _triple_count_total()

    return reply


# noinspection PyUnusedLocal
def used_space_per_org(context, data_dict=None):
    """
    Returns stats for all 3 components for all organizations separately.
    Specifically:
        - filesystem: number of bytes used
        - database: number of bytes used
        - triplestore: number of triplets stored

    Structure of reply:
    {
        '<organization_id>': {
            'filesystem': <long>,
            'database': <long>,
            'triplestore': <long>
        },
    }

    :param context: standard CKAN action API context instance
    :param data_dict: additional parameters (not used)
    :return: JSON reply
    """
    reply = {}

    _filesystem_space_per_org(context, reply)
    _database_space_per_org(context, reply)
    _triple_count_per_org(context, reply)

    return reply


def _triple_count_total():
    sparql = SPARQLWrapper(SPARQL_ENDPOINT)
    sparql.setQuery("""
        SELECT count(*) AS ?count
        WHERE { ?s ?p ?o . }
    """)

    sparql.setReturnFormat(JSON)
    results = sparql.query().convert()

    for result in results["results"]["bindings"]:
        return long(result["count"]["value"])


def _get_graph_list():
    sparql = SPARQLWrapper(SPARQL_ENDPOINT)
    sparql.setQuery("""
        SELECT DISTINCT ?g
        WHERE { GRAPH ?g { ?s ?p ?o . }}
    """)
    sparql.setReturnFormat(JSON)
    results = sparql.query().convert()

    return [str(result['g']['value']) for result in results['results']['bindings']]


def _get_graph_triple_count(graph_iri):
    sparql = SPARQLWrapper(SPARQL_ENDPOINT)
    sparql.setQuery("""
        SELECT COUNT(*)
        WHERE { ?s ?p ?o . }
    """)
    sparql.addDefaultGraph(graph_iri)
    sparql.setReturnFormat(JSON)
    results = sparql.query().convert()

    return long(results['results']['bindings'][0]['callret-0']['value'])


def _triple_count_per_org(context, reply):
    # requires iODBC with Virtuoso driver to be installed and configured
    # see ~/.odbc.ini

    # loads list of users with write permissions for the specified graph IRI
    graph_owners = '''
        SELECT
            u.U_ID,
            u.U_NAME
        FROM
            "DB"."DBA"."SYS_USERS" as u,
            "DB"."DBA"."RDF_GRAPH_USER" as gu,
            "DB"."DBA"."RDF_IRI" as iri
        WHERE
            u.U_ID = gu.RGU_USER_ID AND         -- join SYS_USERS with RDF_GRAPH_USER
            gu.RGU_GRAPH_IID = iri.RI_ID AND    -- join RDF_GRAPH_USER with RDF_IRI
            gu.RGU_PERMISSIONS >= 3 AND         -- only >= write permissions
            iri.RI_ID = iri_to_id(?, 0)         -- for the specified graph IRI
    '''

    list_of_orgs = get_action('organization_list')(context, {'all_fields': True})
    list_of_orgs_by_names = {}
    for o in list_of_orgs:
        org_name = o['name']
        if org_name not in list_of_orgs_by_names:
            list_of_orgs_by_names[org_name] = o

    cnxn = pyodbc.connect(VIRTUOSO_DSN)
    for graph_iri in _get_graph_list():
        cursor = cnxn.cursor()
        cursor.execute(graph_owners, (graph_iri, ))
        row = cursor.fetchone()

        if row is not None:
            log.debug('graph_iri = {0}, user_id = {1}, user_name = {2}'.format(graph_iri, row[0], row[1]))

            user_name = row[1]
            if user_name in list_of_orgs_by_names:
                org_id = list_of_orgs_by_names[user_name]['id']
                graph_size = _get_graph_triple_count(graph_iri)
                if org_id not in reply:
                    reply[org_id] = _get_empty()
                reply[org_id]['triplestore'] += long(graph_size)

        cursor.close()
    return


def _database_space_per_org(context, reply):
    table_size_query = u'''
    SELECT
        table_name,
        pg_total_relation_size(table_name)
    FROM
        information_schema.tables
    WHERE
        table_schema = :schema'''

    # get sizes of all database tables in schema
    table_sql = sqlalchemy.text(table_size_query)
    data_dict = {'connection_url': pylons.config['ckan.datastore.read_url']}
    # noinspection PyProtectedMember
    results = db._get_engine(data_dict).execute(table_sql, schema=CKAN_DATASTORE_SCHEMA).fetchall()

    # use only tables from datastore API
    table_list = _list_of_datastore_tables(context)
    results = [(name, size) for (name, size) in results if name in table_list]

    # map tables/resources to org ids
    resource_to_org = _resource_to_org_mapping(context)
    for (resource_id, size) in results:
        org_id = resource_to_org[resource_id]
        if org_id not in reply:
            reply[org_id] = _get_empty()
        reply[org_id]['database'] += long(size)


def _resource_to_org_mapping(context):
    resource_to_org = {}
    for dataset in get_action('current_package_list_with_resources')(context, {}):
        for resource in dataset['resources']:
            resource_to_org[resource['id']] = dataset['organization']['id']
    return resource_to_org


def _list_of_datastore_tables(context):
    data_dict = {'resource_id': '_table_metadata'}
    datastore_tables = get_action('datastore_search')(context, data_dict)['records']
    return [t[u'name'] for t in datastore_tables if t[u'name'] != u'_table_metadata']


def _filesystem_space_per_org(context, reply):
    for dataset in get_action('current_package_list_with_resources')(context, {}):
        dataset_size = sum([_file_size(r) for r in dataset['resources'] if h.url_is_local(r['url'])])
        organization_id = dataset['organization']['id']
        if organization_id not in reply:
            reply[organization_id] = _get_empty()
        reply[organization_id]['filesystem'] += long(dataset_size)


def _get_empty():
    return dict.copy(EMPTY)


def _file_size(resource):
    upload = uploader.ResourceUpload(resource)
    return os.path.getsize(upload.get_path(resource['id']))


class StorageAdminPlugin(plugins.SingletonPlugin):
    plugins.implements(plugins.IActions)

    # noinspection PyMethodMayBeStatic
    def get_actions(self):
        return {'used_space': used_space,
                'used_space_per_org': used_space_per_org}
