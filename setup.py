from setuptools import setup, find_packages

setup(
    name="project_catalog",
    version="0.1",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'flask',
        'celery',
        'dropbox',
        'minio',
        'sqlalchemy',
        'pytest',
        'pytest-flask',
    ],
)