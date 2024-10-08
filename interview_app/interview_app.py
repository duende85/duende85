import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import os
import subprocess

# Use st.write with HTML and CSS to set the width
st.write("""
    <style>
        .full-width {
            max-width: 100%;
        }
    </style>
""", unsafe_allow_html=True)

# Use st.write to display content with the specified class
st.write('<div class="full-width">Your content here</div>', unsafe_allow_html=True)

# Define CSV file paths
customers_csv_path = 'customers.csv'
orders_csv_path = 'orders.csv'

# Load data from CSV files
customers_df = pd.read_csv(customers_csv_path)
orders_df = pd.read_csv(orders_csv_path, parse_dates=[0])

# Initialize the in-memory SQLite database
conn = sqlite3.connect(':memory:')
customers_df.to_sql('customers', conn, if_exists='replace', index=False)
orders_df.to_sql('orders', conn, if_exists='replace', index=False)

# Function to save the DataFrame back to CSV and commit to GitHub
def save_to_csv_and_commit(df, csv_path):
    df.to_csv(csv_path, index=False)
    try:
        subprocess.run(['git', 'add', csv_path], check=True)
        subprocess.run(['git', 'commit', '-m', f'Update {csv_path}'], check=True)
        subprocess.run(['git', 'push'], check=True)
    except subprocess.CalledProcessError as e:
        st.error(f'Error during Git operations: {e}')

# Dictionary to store usernames and passwords
users = {
    "test1": "EVS2024sql",
    "leo": "leoleo",
    "alan": "alaaan2024",
    "admin": "kaczka",
    "candidate": "SQLtest1"
    # Add more users as needed
}

# User authentication
def authenticate(username, password):
    # Check if the username exists in the dictionary
    if username in users:
        # Retrieve the stored password for the username
        stored_password = users[username]
        # Check if the provided password matches the stored password
        if password == stored_password:
            return True  # Authentication successful
    return False  # Authentication failed

# Streamlit UI
st.title('SQL Test')

# Login form
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    username = st.text_input('Username')
    password = st.text_input('Password', type='password')
    if st.button('Login'):
        if authenticate(username, password):
            st.session_state.logged_in = True
            st.session_state.username = username
            st.success('Logged in successfully')
        else:
            st.error('Invalid username or password')
else:
    st.write(f'Welcome, {st.session_state.username}!')
    st.write('You are a data analyst at an e-commerce company. Your manager has asked you to analyze the orders placed by customers in the North America region. You need to identify the most recent order for each customer in North America and provide details about the customer and their order.')
    st.write('The data is stored in the tables named **customers** and **orders**.')
    # Input for SQL query
    query = st.text_area('Enter your SQL query here:', 'SELECT * FROM customers')

    # Execute the query and display the result
    if st.button('Run Query'):
        try:
            result = pd.read_sql_query(query, conn)
            st.write(result)
            st.write(query)
            
            # Save changes to the database back to CSV if modifying queries are detected
            if query.strip().lower().startswith(('update', 'delete', 'insert')):
                customers_df_updated = pd.read_sql_query('SELECT * FROM customers', conn)
                orders_df_updated = pd.read_sql_query('SELECT * FROM orders', conn)
                if username == "admin":
                    save_to_csv_and_commit(customers_df_updated, customers_csv_path)
                    save_to_csv_and_commit(orders_df_updated, orders_csv_path)
        except Exception as e:
            st.error(f'Error: {e}')

    # Logout button
    if st.button('Logout'):
        st.session_state.logged_in = False
        st.session_state.username = None
        st.success('Logged out successfully')

# Close the connection when done
conn.close()
