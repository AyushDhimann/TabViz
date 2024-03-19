import requests
from xml.etree import ElementTree as ET
import os
import shutil
import zipfile
import re
import csv
import google.generativeai as genai
import tableauserverclient as TSC
from IPython.display import display, HTML
import importlib.resources
import pandas as pd
import random
import string
import hashlib

file_in_static_folder = importlib.resources.files('tabviz').joinpath(os.path.join('static', 'example.twbx'))
destination_folder = os.getcwd()
tabviz_folder = os.path.join(destination_folder, 'tabviz')
if not os.path.exists(tabviz_folder):
    os.makedirs(tabviz_folder)
destination_file = os.path.join(tabviz_folder, "example.twbx")
shutil.copy(file_in_static_folder, destination_file)


def tableau_online_signin(site,site_id,token_name,token_secret,api_version):
    signin_url = f'https://{site}/api/{api_version}/auth/signin'
    signin_xml = f'''
    <tsRequest>
      <credentials personalAccessTokenName="{token_name}" personalAccessTokenSecret="{token_secret}">
        <site contentUrl="{site_id}" />
      </credentials>
    </tsRequest>
    '''
    # print(signin_url,signin_xml)
    response = requests.post(signin_url, data=signin_xml, headers={'Content-Type': 'text/xml'})
    if response.status_code == 200:
        root = ET.fromstring(response.text)
        credentials = root.find('.//t:credentials', namespaces={'t': 'http://tableau.com/api'})
        token = credentials.get('token')
        site_id = credentials.find('.//t:site', namespaces={'t': 'http://tableau.com/api'}).get('id')
        print(f'Successfully signed in. Token: {token}, Site ID: {site_id}')
        workbooks_url = f'https://{site}/api/{api_version}/sites/{site_id}/workbooks'
        response = requests.get(workbooks_url, headers={'X-Tableau-Auth': token})
        if response.status_code == 200:
            root = ET.fromstring(response.text)
            workbooks = root.findall(".//{http://tableau.com/api}workbook")
            global project_id
            for workbook in workbooks:
                workbook_id = workbook.get('id')
                workbook_name = workbook.get('name')
                project_element = workbook.find(".//{http://tableau.com/api}project")
                project_id = project_element.get('id') if project_element is not None else None
                # print(f"Workbook ID: {workbook_id}, Workbook Name: {workbook_name}, Project ID: {project_id}")
        else:
            print(f'Failed to query workbooks. Status Code: {response.status_code}')
    else:
        print(f'Failed to sign in. Status Code: {response.status_code}')


def process_file(file_path):
    tabviz_folder = os.path.join(os.path.dirname(file_path), "tabviz")
    os.makedirs(tabviz_folder, exist_ok=True)
    with zipfile.ZipFile(shutil.copyfile(file_path, os.path.join(tabviz_folder, os.path.basename(file_path).replace(".twbx", ".zip"))), 'r') as zip_ref:
        zip_ref.extractall(tabviz_folder)
    for root, dirs, files in os.walk(tabviz_folder):
        for file in files:
            if file.endswith(".twb"):
                shutil.copyfile(os.path.join(root, file), os.path.join(root, file).replace(".twb", ".xml"))

def extract_table_contents_from_file(file_path):
    global table_contents
    with open(file_path, 'r') as file:
        content = file.read()
        tables = re.findall(r'<worksheets>(.*?)</worksheets>', content, re.DOTALL)
        for table in tables:
            table_contents += table.strip()


def extract_table_contents_from_file_for_column(file_path):
    global table_contents_column
    with open(file_path, 'r') as file:
        content = file.read()
        tables = re.findall(r'<objects>(.*?)</objects>', content, re.DOTALL)
        for table in tables:
            table_contents_column += table.strip()


def replace_data_in_csv(source_csv, destination_csv):
    pd.read_csv(source_csv).to_csv(destination_csv, index=False)


def extract_random_values(csv_file):
    try:
        with open(csv_file, 'r', newline='') as file:
            reader = csv.DictReader(file)
            data, columns = [row for row in reader if any(row.values())], reader.fieldnames
        return '\n'.join(f"{column}: {' '.join(random.sample([row[column] for row in data if row[column]], min(8, len(data))))}" for column in columns)
    except Exception as e:
        return f"An error occurred: {str(e)}"

def setup_generative_model_column(api_key,erv,table_contents):
    genai.configure(api_key=api_key)
    generation_config = {
        "temperature": 0.4,
        "top_p": 1,
        "top_k": 1,
        "max_output_tokens": 3048,
    }

    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    ]

    model = genai.GenerativeModel(model_name="gemini-1.0-pro", generation_config=generation_config,
                                  safety_settings=safety_settings)
    return model

def start_conversation_column(model,erv,table_contents):
    convo = model.start_chat(history=[])
    msg = f"""
Dataset:

{erv}

XML:

{table_contents}


Command:

Now i want you to write me back the xml file, modified in the same format as the above sample, with the column names changed as per the Dataset also provided above , and create visualizations, based on the best possible match for column names, which would make the most sense to be shown in the visualization. Focus on datasource-dependencies ,rows,panes and other important fields, make sure values are changed as they should be everywhere all at once. Also the output should only be the correct output xml.
"""
    convo.send_message(msg)
    global xml_Data
    xml_Data = convo.last.text

def run_generative_model(api_key,erv,table_contents):
    model = setup_generative_model_column(api_key,erv,table_contents)
    start_conversation_column(model,erv,table_contents)

def calculate_file_hash(file_path):
    with open(file_path, 'rb') as file:
        file_hash = hashlib.sha256(file.read()).hexdigest()
    return file_hash

def read_file_content(file_path):
    with open(file_path, 'r') as file:
        content = file.read()
    return content


def write_content_to_file(file_path, content):
    with open(file_path, 'w') as file:
        file.write(content)

def setup_generative_model(api_key,erv,table_contents_column):
    genai.configure(api_key=api_key)
    generation_config = {
        "temperature": 0.5,
        "top_p": 1,
        "top_k": 1,
        "max_output_tokens": 4096,
    }

    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    ]

    model = genai.GenerativeModel(model_name="gemini-1.0-pro", generation_config=generation_config,
                                  safety_settings=safety_settings)
    return model

def start_conversation(model,erv,table_contents_column):
    convo = model.start_chat(history=[])
    convo.send_message(f"""
Dataset:

{erv}

XML Format:

{table_contents_column}


Command:

As per the given dataset, i need you to write me a XML code in the same format as given above. The XML code should follow the same formatting, and this should be done for all column names. you are allowed to use, integer, string, boolean, real for datatype.Do not rename the csv file, it's name is Product.csv and should be always.
""")
    global xml_column_data
    xml_column_data = convo.last.text
    # print("XMLLLL",xml_column_data)
    return xml_column_data

def run_with_api_key(api_key,erv,table_contents_column,xml_column_data):
    temp_file_path = os.path.join(tabviz_folder, "tabviz", "Data", "1vib26g1r4ena71b8a85o12srz3b", "Product.csv")
    hash_file_path = os.path.join(tabviz_folder, "hash.txt")
    output_file_path = os.path.join(tabviz_folder, "output.txt")
    prev_hash = None

    if os.path.exists(hash_file_path):
        # Read the previous hash from file
        prev_hash = read_file_content(hash_file_path).strip()


    if os.path.exists(temp_file_path):
        current_hash = calculate_file_hash(temp_file_path)

        write_content_to_file(hash_file_path, current_hash)


        if prev_hash is None or prev_hash != current_hash:
            model = setup_generative_model(api_key,erv,table_contents_column)
            output = start_conversation(model,erv,table_contents_column)


            xml_column_data = output


            write_content_to_file(output_file_path, output)
        else:

            output = read_file_content(output_file_path)
            xml_column_data = output

    return xml_column_data

def replace_table_contents_with_xml_data(file_path, xml_data):
    with open(file_path, 'r') as file:
        input_text = file.read()
    new_text = re.sub(r'<worksheet name=\'Sheet 4\'>.*?</worksheet>', xml_data, input_text, flags=re.DOTALL)
    with open(file_path, 'w') as file:
        file.write(new_text)


def replace_table_contents_with_xml_data_for_columns(file_path, xml_column_data):
    with open(file_path, 'r') as file:
        input_text = file.read()
    new_text = re.sub(r"<object caption='Products.csv' id='Products.csv_80C823165E104D25B4F6E7037DA60826'>.*?</object>", xml_column_data, input_text, flags=re.DOTALL)
    with open(file_path, 'w') as file:
        file.write(new_text)


def process_file_repack(tabviz_folder):
    parent_dir = os.path.dirname(tabviz_folder)
    example_xml_file = os.path.join(tabviz_folder, "tabviz", "example.xml")
    example_twb_file = os.path.join(tabviz_folder, "tabviz", "example.twb")

    if os.path.exists(example_xml_file):
        with open(example_xml_file, 'r') as xml_file:
            xml_content = xml_file.read()
        with open(example_twb_file, 'w') as twb_file:
            twb_file.write(xml_content)

    zip_filename = "Data.twbx"
    zip_path = os.path.join(parent_dir, zip_filename)
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        zipf.write(example_twb_file, arcname=os.path.basename(example_twb_file))
        data_folder = os.path.join(tabviz_folder, "tabviz", "Data")
        if os.path.exists(data_folder):
            for root, dirs, files in os.walk(data_folder):
                for file in files:
                    relative_path = os.path.relpath(os.path.join(root, file), data_folder)  # Adjusting relative_path
                    arcname = os.path.join("Data", relative_path)  # Adjusting arcname
                    zipf.write(os.path.join(root, file), arcname=arcname)

    final_zip_path = os.path.join(parent_dir, zip_filename)
    os.replace(zip_path, final_zip_path)



def publish_workbook(token_name,token_secret, site_id, project_id, workbook_name, path_to_workbook,site):
    auth = TSC.PersonalAccessTokenAuth(token_name=token_name, personal_access_token=token_secret, site_id=site_id)
    server = TSC.Server(f"https://{site}", use_server_version=True)

    with server.auth.sign_in(auth):
        new_workbook = TSC.WorkbookItem(project_id, name=workbook_name)
        file_path = os.path.join(tabviz_folder, "hash.txt")
        try:
            new_workbook = server.workbooks.publish(new_workbook, path_to_workbook, 'CreateNew')
        except Exception as e:
            print(f"An error occurred: {e}")
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"File '{file_path}' deleted successfully.")
            else:
                print(f"File '{file_path}' does not exist.")

        print(f'Successfully published workbook {new_workbook.id} to the server.')

def display_tableau_viz(src):
    display(HTML(f"""
    <script type='module' src='https://prod-apnortheast-a.online.tableau.com/javascripts/api/tableau.embedding.3.latest.min.js'></script>
    <tableau-viz id='tableau-viz' src={src} style='width:100%; height:100%;' toolbar='bottom'></tableau-viz>
    """))

def construct_url(site, site_id,workbook_name):
    global src
    src = f"https://{site}/#/site/{site_id}/views/{workbook_name}/Sheet4"
    print("Sharable URL : ", src)
    return src

def generate_random_text(length):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


def main():
    tableau_online_signin(site,site_id,token_name,token_secret,api_version)
    process_file(destination_file)
    extract_table_contents_from_file(xml_file)
    extract_table_contents_from_file_for_column(xml_file)
    replace_data_in_csv(csv_file,dataset)
    erv = extract_random_values(csv_file)
    run_generative_model(api_key,erv,table_contents)
    run_with_api_key(api_key,erv,table_contents_column,xml_column_data)
    replace_table_contents_with_xml_data(xml_file, xml_Data)
    replace_table_contents_with_xml_data_for_columns(xml_file,xml_column_data)
    process_file_repack(tabviz_folder)
    url = construct_url(site, site_id, workbook_name)
    publish_workbook(token_name,token_secret, site_id, project_id, workbook_name, path_to_workbook,site)
    display_tableau_viz(url)

project_id = " "
destination_file = os.path.join(tabviz_folder, "example.twbx")
xml_file = os.path.join(tabviz_folder, "tabviz","example.xml")
dataset = os.path.join(tabviz_folder, "tabviz", "Data", "1vib26g1r4ena71b8a85o12srz3b", "Product.csv")
path_to_workbook = os.path.join(tabviz_folder, "..", "Data.twbx")
table_contents = ""
table_contents_column = ""
xml_column_data = ' '
xml_Data = " "
api_version = '3.22'
workbook_name = generate_random_text(5)
path_to_workbook = os.path.join(tabviz_folder, "..", "Data.twbx")

#ENVS
site_id = os.getenv('site_id')
site = os.getenv('site')
token_name = os.getenv('token_name')
token_secret = os.getenv('token_secret')
csv_file = os.getenv('csv')
api_key = os.getenv('api_key')

if __name__ == "__main__":
    main()