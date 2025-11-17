"""Setup configuration for the replication package."""

from setuptools import find_packages, setup

setup(
    name="aurora-snowflake-replication",
    version="1.0.0",
    description="Aurora PostgreSQL to Snowflake batch replication system",
    author="John B. Roberts",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.11",
    install_requires=[
        "psycopg2-binary==2.9.9",
        "snowflake-connector-python==3.7.0",
        "hvac==2.1.0",
        "boto3==1.34.0",
        "botocore==1.34.0",
        "requests==2.31.0",
    ],
)

