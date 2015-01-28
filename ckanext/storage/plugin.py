import os
import pylons
import sqlalchemy
import ckan.logic as logic
import ckan.plugins as plugins
import ckan.lib.uploader as uploader
import ckanext.datastore.db as db
import logging

from ckan.lib.base import h

log = logging.getLogger('ckanext')
get_action = logic.get_action

# always use _get_empty() to create a copy
EMPTY = {'filesystem': 0L, 'database': 0L, 'triplestore': 0L}
DATASTORE_SCHEMA = 'public'


def used_space(context, data_dict=None):
    """
    Returns used space or count in all 3 components aggregated for all organizations.
    Component is one of filesystem, database, triplestore.

    For filesystem and database, used space in bytes is reported. For triplestore, it's the number
    of graphs the organization uses.

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
        reply['triplestore'] += long(sizes['triplestore'])

    return reply


# noinspection PyUnusedLocal
def used_space_per_org(context, data_dict=None):
    """
    Returns used space or count in all 3 components for all organizations.
    Component is one of filesystem, database, triplestore.

    For filesystem and database, used space in bytes is reported. For triplestore, it's the number
    of graphs the organization uses.

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
    _triplet_count_per_org(context, reply)

    return reply


def _triplet_count_per_org(context, reply):
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
    results = db._get_engine(data_dict).execute(table_sql, schema=DATASTORE_SCHEMA).fetchall()

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
