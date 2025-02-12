#!/usr/bin/env python
# coding: utf-8

# # DataverseNL Analysis at UM
# 
# ---
# 
# This script connects to the DataverseNL instance at Maastricht University and generates reports on the available datasets. The pipeline is divided into three sections: Connection, Processing, and Reporting.
# 
# Contact: rdm-services@ma.nl  
# License: MIT License  
# Documentation: [pyDataverse](https://pydataverse.readthedocs.io/)
# 

import os
import pandas as pd
from pyDataverse.api import NativeApi
import requests
import json
from datetime import datetime

# Utility function to generate filenames with timestamps
def generate_filename(base_name, extension):
    date_str = datetime.now().strftime("%Y%m%d")
    return f"{base_name}-{date_str}.{extension}"

DATAVERSE_URL = 'https://dataverse.nl/dataverse/maastricht'

# You need a token from Dataverse (store in TOKEN.txt)
with open('TOKEN.txt', 'r') as file:
    API_TOKEN = file.read().strip()

BASE_URL = DATAVERSE_URL.split('/dataverse/')[0]
DATAVERSE_ID = DATAVERSE_URL.split('/dataverse/')[1]

# Connect to the API
api = NativeApi(BASE_URL, API_TOKEN)

# Test the connection
resp = api.get_info_version()
assert resp.json()['status'] == 'OK', "Failed to connect to Dataverse API"
print('Successful connection to DataverseNL API!!')

json_file = generate_filename('dataverse_tree', 'json')
json_path = f'data/{json_file}'

# If the JSON file doesn't exist, fetch data from Dataverse API and save it
if not os.path.exists(json_path):
    # Fetch the data from the API and store it as `tree_data`
    tree_data = api.get_children(DATAVERSE_ID, children_types=['dataverses', 'datasets'])

    # Save the fetched data to a JSON file
    with open(json_path, 'w') as f:
        json.dump(tree_data, f)

    # Load the `tree` from the fetched data
    tree = tree_data
else:
    # If the file exists, load the tree from the JSON file
    with open(json_path, 'r') as f:
        tree = json.load(f)

# Function to retrieve datasets from a dataverse
def get_datasets(dataverse):
    dataverse_id = dataverse['dataverse_id']
    headers = {"X-Dataverse-key": API_TOKEN}
    url = f"{BASE_URL}/api/dataverses/{dataverse_id}/contents"
    response = requests.get(url, headers=headers)
    response_json = response.json()
    
    if 'data' not in response_json:
        print(f"Data key not found for {dataverse_id}")
        return {'data': []}
    
    return response_json

# Function to recursively process datasets, handling both departments and sub-departments
def process_datasets(parent_name, children, datasets_list, department_name):
    for child in children:
        if child['type'] == 'dataverse':
            sub_dataverse_name = child['title']
            datasets = get_datasets(child)
            for dataset in datasets['data']:
                publicationDate = dataset.get('publicationDate')
                persistent_url = dataset.get('persistentUrl')
                if publicationDate and persistent_url:
                    dataset_info = {
                        'faculty': parent_name,
                        'department': department_name,
                        'sub_dataverse': sub_dataverse_name,
                        'year': publicationDate[0:4],
                        'date': publicationDate,
                        'persistentUrl': persistent_url
                    }
                    datasets_list.append(dataset_info)

            # Recursive call: If the sub-department has sub-departments
            if 'children' in child and child['children']:
                process_datasets(parent_name, child['children'], datasets_list, department_name)

# Main extraction logic
datasets_list = []
for faculty in tree:
    if faculty['type'] != 'dataverse':
        continue
    faculty_name = faculty['title']
    has_departments = False

    # Process departments if they exist
    for department in faculty['children']:
        if department['type'] != 'dataverse':
            continue
        has_departments = True
        department_name = department['title']
        datasets = get_datasets(department)
        for dataset in datasets['data']:
            publicationDate = dataset.get('publicationDate')
            persistent_url = dataset.get('persistentUrl')
            if publicationDate and persistent_url:
                dataset_info = {
                    'faculty': faculty_name,
                    'department': department_name,
                    'sub_dataverse': 'No sub-dataverse',  # Default to "no sub-dataverse" at department level
                    'year': publicationDate[0:4],
                    'date': publicationDate,
                    'persistentUrl': persistent_url
                }
                datasets_list.append(dataset_info)

        # Check if department has sub-departments and process recursively
        if 'children' in department and department['children']:
            process_datasets(faculty_name, department['children'], datasets_list, department_name)

    # If no departments, process datasets directly under the faculty
    if not has_departments:
        department_name = 'No department'
        datasets = get_datasets(faculty)
        for dataset in datasets['data']:
            publicationDate = dataset.get('publicationDate')
            persistent_url = dataset.get('persistentUrl')
            if publicationDate and persistent_url:
                dataset_info = {
                    'faculty': faculty_name,
                    'department': department_name,
                    'sub_dataverse': 'No sub-dataverse',  # No sub-department
                    'year': publicationDate[0:4],
                    'date': publicationDate,
                    'persistentUrl': persistent_url
                }
                datasets_list.append(dataset_info)

# Convert to DataFrame
df = pd.DataFrame(datasets_list)

# Save the DataFrame to Excel
overview_file = generate_filename('dataverse_overview', 'xlsx')
df.to_excel(f'data/{overview_file}')

# Test if data was successfully loaded
assert not df.empty, "No datasets found."
print(f"Datasets loaded: {len(df)}")

faculty_dict = {
    'Faculty of Psychology and Neuroscience': 'FPN',
    'School of Business and Economics': 'SBE',
    'Faculty of Health, Medicine & Life Sciences': 'FHML',
    'Faculty of Arts and Social Sciences': 'FASoS',
    'Faculty of Law': 'FdR',
    'Faculty of Science and Engineering': 'FSE',
    'UNU-MERIT': 'UNU-MERIT',
    'DataHub': 'MUMC+',
    'Maastricht UMC+': 'MUMC+'
}

df.faculty = df.faculty.replace(faculty_dict)
df['count'] = 1
df_grouped = df.groupby(['faculty', 'year'])['count'].sum().reset_index()
df_pivot = df_grouped.pivot(index='faculty', columns='year', values='count').fillna(0)

absolute_file = generate_filename('dataverse_absolute', 'xlsx')
df_pivot.to_excel(f'data/{absolute_file}')

df_relative = df_pivot.apply(lambda x: (x / x.sum() * 100).round(2), axis=1)
relative_file = generate_filename('dataverse_relative', 'xlsx')
df_relative.to_excel(f'data/{relative_file}')

print(f"Absolute data saved to: {absolute_file}")
print(f"Relative data saved to: {relative_file}")

