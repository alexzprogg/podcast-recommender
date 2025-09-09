from etl import main_input_processing
import numpy as np
from flask import Flask,render_template,request,jsonify, flash, url_for, redirect, session
import sqlite3
from nlp import create_recommendation
from etl import eliminate_plural_trivial_words
from bs4 import BeautifulSoup 
import requests
import pickle
import os

def get_backend_result(user_inputs):
    clean_keyword_pool = main_input_processing(user_inputs)
    print("user inputs ... "+str(user_inputs))
    print("main processing: ..." +str(clean_keyword_pool))
    c2_relevance,similar_word = create_recommendation(clean_keyword_pool, user_inputs)
    print("create recommendation: ..." +str(c2_relevance)+"  "+str(similar_word))
    return c2_relevance,similar_word,user_inputs,clean_keyword_pool

def check_user_input(input1,input2,input3):
    error = []
    error_msg = ""
    user_inputs = [input1,input2,input3]
    user_inputs = eliminate_plural_trivial_words(user_inputs)
    if len(user_inputs)<=2:    
        is_redirect = True
        print("must enter 3 keywords")
        error_msg = "must enter 3 keywords"
        error.append(error_msg)
        return is_redirect,error,user_inputs
    
    for input in user_inputs:
        if input == "":
            is_redirect = True
            error_msg = "Input contains a stopword. Please try again."
            error.append(error_msg)
            return is_redirect,error,user_inputs
    
    
    result = {} #dictionary
    for each_input in user_inputs: 
        iserror = 0
        base_url = 'https://podcasts.google.com/search/'
        search_url = base_url + each_input 
        resp = requests.get(search_url)
        soup = BeautifulSoup(resp.text, 'lxml') #utilizes google podcast api to search for podcast results 
        div_list = soup.find_all('div', class_="O9KIXe") #check if no podcast found using class property as web-scraping tool
        if len(div_list)!=0: #meaning that within class, there is a line: "no podcast found". So, the input is invalid
            iserror = 1
        result[each_input] = iserror

    is_redirect = False
    error = []
    for key in result.keys():
        if result[key] == 1:
            error_msg = f"Input {key} is invalid. Please try again."
            error.append(error_msg)
    if error_msg !="":
        is_redirect = True
    return is_redirect, error, user_inputs

if __name__ == '__main__': #removes redundancies of rerunning models etc. increases efficiency 
    
    app = Flask(__name__)
    app.secret_key = "super secret key"
 
    @app.route('/')
    def form(): 
        template_name = 'form.html'
        conn = sqlite3.connect('data/KEYWORD_MAP.db')
        conn.row_factory = sqlite3.Row  # index-based and case-insensitive name-based access to columns; converts plain tuple to more useful object
        print("Connected to the database successfully")
        # Create a cursor for interacting with the database
        cur = conn.cursor()
        cur.execute('CREATE TABLE IF NOT EXISTS KEYWORD(user_input, keywords)')
        conn.commit()
        # Execute a query to fetch data from the 'KEYWORD' table
        cur.execute('SELECT user_input FROM KEYWORD')
        input_records = cur.fetchall()
        input_records = [input_record[0] for input_record in input_records]
        return render_template(template_name, input_records=input_records) #renders the frontend 
    
    @app.route('/previous_inputs', methods = ['POST']) # Route to display data from the 'KEYWORD' table
    def previous_inputs(): #query the data, grab the data and pass it on to form.html template 
        template_name = 'previous_inputs.html'
        # Connect to the SQLite database
        conn = sqlite3.connect('data/KEYWORD_MAP.db')
        conn.row_factory = sqlite3.Row  # index-based and case-insensitive name-based access to columns; 
        #converts plain tuple to more useful object
        print("Connected to the database successfully")

        # Create a cursor for interacting with the database
        cur = conn.cursor()
        cur.execute('CREATE TABLE IF NOT EXISTS KEYWORD(user_input, keywords)')
        conn.commit()
        # Execute a query to fetch data from the 'KEYWORD' table
        cur.execute('SELECT user_input, keywords FROM KEYWORD')
        # Fetch all records from the query result and convert to a list of dictionaries
        records = cur.fetchall()
        keywords = [dict(user_input=record[0], keywords=record[1]) for record in records]
        #This makes it easier to work with the data in a more structured way

        # Close the database connection
        conn.close()

        # Pass the data to the HTML template
        return render_template(template_name, keywords=keywords)
    
    @app.route('/query_user_input', methods=['POST'])
    def query_user_input():
        request_data = request.get_json()  # Get JSON data from the request body
        if 'user_query' in request_data:
            search_input = request_data['user_query']
            conn = sqlite3.connect('data/KEYWORD_MAP.db')
            cur = conn.cursor()
            cur.execute('SELECT keywords FROM KEYWORD WHERE user_input = ?', (search_input,))
            query_keywords = cur.fetchone()
            query_keywords = query_keywords[0]
            query_keywords = query_keywords.split(",")
            if query_keywords is not None:
                session['keyword'] = query_keywords
                search_input = ''.join(search_input)
                session['searchQuery'] = search_input
                session['route'] = 1
                #keywordVector = word_to_vector(query_keywords)
                return "success"
                #return render_template('embedding_projector.html', query_keywords = query_keywords)
            else:
                print("No data found for the given input")
                return jsonify({'error': 'No data found for the given input'}), 404  # Return a 404 Not Found status code
        else:
            print("user_query not in request_data")
            return jsonify({'error': 'No user_query provided'}), 400  # Return a 400 Bad Request status code

    @app.route('/input_validation', methods = ['POST'])
    def input_validation():
        form_data = request.form #requesting the input data from form
        input_1, input_2, input_3 = form_data['Input1'],form_data['Input2'],form_data['Input3'] 
        is_redirect, error, user_inputs = check_user_input(input_1,input_2,input_3)
        if is_redirect == False and len(user_inputs)==3:
            input_1 = user_inputs[0]
            input_2 = user_inputs[1]
            input_3 = user_inputs[2]
            session['user_input'] = [input_1, input_2, input_3] #session: datalog for individual users acts as a dictionary
            return redirect(url_for('loading')) #redirects to loading page 
        else:
            for error_msg in error: 
                flash(f'{error_msg}')
            #return render_template(template_name) #re enter data 
            return redirect(url_for('form'))
        
    @app.route('/loading')
    def loading():
        template_name = 'loading.html'
        return render_template(template_name)

    @app.route('/backend')
    def backend():
        user_inputs = session.get('user_input') #get input from session 
        c2_relevance,similar_word,user_inputs,clean_keyword_pool = get_backend_result(user_inputs) #backend processing
        data = {
            "c2_relevance": c2_relevance,
            "similar_word": similar_word,
            "clean_keyword_pool": clean_keyword_pool,
            "user_inputs": user_inputs
        }
        session['result'] = pickle.dumps(data)
        return "Success"

    @app.route('/result')
    def result():
        template_name = 'result.html'
        result_data = session['result']
        session['route'] = 0
        if result_data:
            # Unpickle the data to get the variables
            try:
                loaded_data = pickle.loads(result_data)
                c2_relevance = loaded_data.get('c2_relevance')
                similar_word = loaded_data.get('similar_word')
                clean_keyword_pool = loaded_data.get('clean_keyword_pool')
                user_inputs = loaded_data.get('user_inputs')
                # Now you can use these variables

                #flatten list of list into list 
                keyword_pool = []
                for i in clean_keyword_pool:
                    keyword_pool.extend(i)
                clean_keyword_pool = keyword_pool 
                
                # Generate the URL for the embedding_projector route with clean_keyword_pool as a query parameter
                word_cloud_url = url_for('word_cloud')
                session['keyword'] = clean_keyword_pool
                inputs = str(user_inputs[0])+" , "+str(user_inputs[1])+" , "+str(user_inputs[2])
                flash(inputs)
                flash(similar_word)
                flash("{:.2%}".format(c2_relevance))
                similar_word = str(similar_word)
                base_url = 'https://podcasts.google.com/search/' 
                search_url = base_url + similar_word 
                flash(search_url)
                return render_template(template_name,c2_relevance=c2_relevance,
                                    similar_word=similar_word, search_url=search_url,bool=[0,1,2,0],
                                    user_inputs=user_inputs,
                                    word_cloud_url=word_cloud_url)
            except (pickle.UnpicklingError, TypeError, ValueError):
                print("Pickle not pickling...")
                # Handle exceptions during unpickling
                pass
    
    @app.route('/word_cloud')
    def word_cloud():
        template_name = 'word_cloud.html'
        clean_keyword_pool = session['keyword'] 
        if session['route'] == 1:
            search_input = session['searchQuery']
            flash(search_input)
            route = 1
        else:
            route = 0
        return render_template(template_name,
                               keywordsForCloud=clean_keyword_pool,route = route)
    app.run(debug=True)

