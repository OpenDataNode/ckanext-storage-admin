from setuptools import setup, find_packages

version = '0.1.0'

setup(
    name='ckanext-storage-admin',
    version=version,
    description="""
    Report filesystem / database / triplestore data usage
    """,
    long_description="""
    Reports data usage through CKAN API as total aggregate and per organization.
    - filesystem: amount of data in bytes used by datasets
    - database: PostgreSQL data in bytes used
    - triplestore: Virtuoso triple count used
    """,
    classifiers=[], # Get strings from http://pypi.python.org/pypi?%3Aaction=list_classifiers
    keywords='',
    author='Viktor Lieskovsky',
    author_email='viktor.lieskovsky@eea.sk',
    url='',
    license='',
    packages=find_packages(exclude=['examples', 'tests']),
    namespace_packages=['ckanext',
                        'ckanext.storage'
                        ],
    package_data={'': []},
    include_package_data=False,
    zip_safe=False,
    install_requires=[
        'SPARQLWrapper>=1.6.4',
        'pypyodbc>=1.3.3'],
    entry_points=\
    """
    [ckan.plugins]
    storage_admin=ckanext.storage.plugin:StorageAdminPlugin
    """,
)