from bs4 import BeautifulSoup 
import pandas as pd 
import podcastparser
import urllib.request
from keybert import KeyBERT
import requests,sqlite3,re
import pickle
import nltk
from nltk.stem import WordNetLemmatizer
nltk.download('wordnet')
nltk.download('omw-1.4')

def get_stop_words():
    with open('data/Stopwords.pickle', 'rb') as handle:
        stopwords = pickle.load(handle)
    return stopwords 

def eliminate_plural_trivial_words(word_list):
    # Define a list of trivial words
    trivial_words = get_stop_words()
    lemmatizer = nltk.stem.WordNetLemmatizer()
    singular_words = []
    for word in word_list:
        if word!="":
            singular_words.append(lemmatizer.lemmatize(word.strip()))
    #singular_words = [lemmatizer.lemmatize(word.strip()) for word in word_list]
    # Remove trivial words 
    cleaned_words = []
    for word in singular_words:
        if word.lower() not in trivial_words and word.lower()!='':
            cleaned_words.append(word.lower())
        else:
            cleaned_words.append("")
    print("singular words: ... "+str(cleaned_words)+str(len(cleaned_words)))
    return cleaned_words
    
def KeywordExtractor(user_input):
    #reading data from database 
    conn = sqlite3.connect('data/KEYWORD_MAP.db')  #connecting to a database
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS KEYWORD(user_input, keywords)')  #creating a database table
    conn.commit()

    df_result = pd.read_sql('SELECT user_input, keywords FROM KEYWORD', conn)
    
    #comparing user_input from database with new user_input
    for index in range(df_result['user_input'].count()):
        if(df_result['user_input'][index]==user_input):
            return(user_input,df_result['keywords'][index])
        
    #if same then return keywords previously found 
        
    #otherwise, go through webscraping process to find keywords
    base_url = 'https://podcasts.google.com/search/'
    search_url = base_url + user_input 
    resp = requests.get(search_url)
    soup = BeautifulSoup(resp.text, 'lxml') 
    #utilizes google podcast api to search for podcast results 

    podcast_urls = []
    results = soup.find_all('a', {'role': 'listitem'}) #find the podcasts items inside of the soup content 
    domain_google_podcast = 'https://podcasts.google.com/'
    for result in results: 
        podcast_url_part = result.get('href')[2:] #get the links of each podcast item 
        podcast_urls.append(domain_google_podcast+podcast_url_part)

    #getting homepage url 
    homepage_urls = []
    for i in podcast_urls:
        resp_home = requests.get(i)                                                                                                                              
        soup_home = BeautifulSoup(resp_home.text, 'lxml')
        home_class = soup_home.find_all('div', {'class': 'Uqdiuc'}) #access the item within homepage class
        for div in home_class:
            homepage_url_part = div.a['href'] #access the homepage URL of each podcast 
            homepage_urls.append(domain_google_podcast+homepage_url_part) 

    #check if homepage_urls in list are the same (first elimination of redundant elements)
    new_homepage_urls = list(set(homepage_urls))

    descriptions = {}
    for pc_url in new_homepage_urls:
        google_podcast_url = pc_url 
        url_getrssfeed = 'https://getrssfeed.com'
        headers = {'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36'}

        #to get podcast homepage rss url  
        r = requests.post(url_getrssfeed, data={"url":google_podcast_url}, headers=headers) 
        soup_getrssafterpost = BeautifulSoup(r.text, 'lxml')
        try: 
            rss_url  = soup_getrssafterpost.find('div', {'class': 'mt-4'}).a['href']
        except: 
            print(f"Cannot retrieve rss feed from this {google_podcast_url}")
            continue
        try:
            parsed = podcastparser.parse(rss_url, urllib.request.urlopen(rss_url))
            #get descriptions for each rss feed episode 
            description = ''
            for i in range (len(parsed['episodes'])): 
                description = description + parsed['episodes'][i]['description']        

            descriptions[parsed['title']] = description 
        except:
            print(f"ERROR in pasring rss url: {rss_url}")   

    total_keywords = []
    for i in descriptions.keys(): 
        kw_model = KeyBERT() #model using tone, word frequency, etc to find keywords from text 
        keywords = kw_model.extract_keywords(descriptions[i])
        total_keywords.append(keywords)

    #making list of list (total_keywords) into string for storing in database
    total_keywords_flat = []
    for item in total_keywords:
        for item2 in item: 
            if item2[0] not in total_keywords_flat:
                total_keywords_flat.append(item2[0])

    total_keywords_string = ",".join(total_keywords_flat)

    #expanding user inputs to create keyword pool using BERT from descriptions of relevant podcasts 
    d = {'user_input': [user_input], 'keywords':[total_keywords_string]}
    df_result = pd.DataFrame(data=d)    
    df_result.to_sql('KEYWORD', conn, if_exists='append', index=False) #put into database
    return(user_input,total_keywords_string)


def main_input_processing(input_results):
    keyword_pool = []
    
    print(f"Receive user inputs: {input_results}")

    for input_result in input_results:
        print(f"Start processing user input: {input_result}...")
        user_input, total_keywords_string = KeywordExtractor(input_result)
        total_keywords_list = total_keywords_string.split(',') #making string into list of keywords seperated by comma
        keyword_pool.append(total_keywords_list) #list of list of keywords from each input 

    print(f"Finished processing user inputs: {input_results}")
    
    clean_keyword_pool = []
    for each_keyword in keyword_pool:
        cleaned_words = eliminate_plural_trivial_words(each_keyword)
        if len(cleaned_words) == 0:  
            continue
        new_cleaned_words = list(set(cleaned_words))
        clean_keyword_pool.append(new_cleaned_words) 
    
    return clean_keyword_pool