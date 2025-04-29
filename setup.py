from setuptools import setup, find_packages

setup(
    name="catalog",
    version="0.1.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
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
