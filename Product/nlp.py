from gensim import models
import numpy as np
import os
file_path = os.path.join(os.getcwd(), 'data', 'glove.6B.300d.txt')
model = models.KeyedVectors.load_word2vec_format(file_path, binary=False, no_header=True)

def word_to_vector(keyword_pool):
    each_keyword_vector_pool = []
    if keyword_pool is None:
        return []  # Return an empty list if keyword_pool is None
    for each_keyword in keyword_pool:
        try:
            # 'model' is your pre-trained Word2Vec model
            vector = model[each_keyword]
            each_keyword_vector_pool.append(vector)
        except KeyError:
            # Handle the case where the keyword is not in the model's vocabulary
            continue
    return each_keyword_vector_pool

def get_centroid_1(keyword_pool):
    keyword_pool_flat = []
    for i in keyword_pool:
        keyword_pool_flat.extend(i) #makes list flat by concatenating list of keywords from each input together 
    
    vector_pool = []
    for i in keyword_pool_flat:
        try:
            vector_pool.append(model[i]) #make into 1x300x(number of keywords) array
        except:
            continue
    #mean        
    vector_pool = np.array(vector_pool, dtype=object)
    print(vector_pool.shape)
    centroid_1 = vector_pool.mean(axis=0)
    distance=0
    for vector in vector_pool:
        distance += np.sqrt(sum((vector-centroid_1)**2))
    avg_distance = distance/len(vector_pool) #average distance
    print(centroid_1.shape,avg_distance,vector_pool.shape)
    return(centroid_1,avg_distance,vector_pool)

def get_centroid_2(keyword_pool):
    total_keyword_vector_pool = []
    pre_centroid_arr = [] 
    for each_keyword_pool in range(len(keyword_pool)): #loop through keyword pool from each homepage 
        each_keyword_vector_pool = []
        for each_keyword in keyword_pool[each_keyword_pool]: #loop through keyword in each keyword pool 
            try:
                each_keyword_vector_pool.append(model[each_keyword]) #list of list 
            except:
                continue        
        each_keyword_vector_pool = np.array(each_keyword_vector_pool, dtype=object) #keyword vectors for each input in a numpy array
        total_keyword_vector_pool.append(each_keyword_vector_pool) #array stored in a nested list for all 3 inputs 
    total_keyword_vector_pool = np.array(total_keyword_vector_pool, dtype=object)
    for keyword_vector_pool in total_keyword_vector_pool:
        pre_centroid_2 = keyword_vector_pool.mean(axis=0) #centroid for each keyword pool of each input
        #print(f"pre_centroid_2: {pre_centroid_2.shape}")
        pre_centroid_arr.append(pre_centroid_2) #store in an array
    print(len(pre_centroid_arr))
    pre_centroid_arr = np.array(pre_centroid_arr, dtype=object)
    centroid_2 = pre_centroid_arr.mean(axis=0) 
    distance = 0
    for arr in range(len(pre_centroid_arr)):
        distance += np.sqrt(sum((pre_centroid_arr[arr]-centroid_2)**2))
    avg_distance = distance/len(pre_centroid_arr)
    print(centroid_2.shape,avg_distance,pre_centroid_arr.shape)
    return(centroid_2,avg_distance,pre_centroid_arr)

def create_recommendation(clean_keyword_pool,user_inputs):
    print("centroid 1: ")
    c1,distance1,vector_pool1=get_centroid_1(clean_keyword_pool)
    print("centroid 2: ")
    c2,distance2,vector_pool2=get_centroid_2(clean_keyword_pool)

    C1_min = 5.697671953672131
    C1_max = 6.826386969517547
    C2_min = 0.9865800996310438
    C2_max = 4.104674641199845

    def C1_min_max_normalisation(C_dis):
        return 1-((C_dis-C1_min)/(C1_max-C1_min)) #normalisation to 0-1, the larger the more relevant 
        
    def C2_min_max_normalisation(C_dis):
        return 1-((C_dis-C2_min)/(C2_max-C2_min))

    c1_relevance,c2_relevance = C1_min_max_normalisation(distance1),C2_min_max_normalisation(distance2)

    final_centroid = c2.reshape(300)
    centroid_input1 = model.similar_by_vector(final_centroid) #matching centroid vector with list of similar words 
    centroid_input1 = np.array(centroid_input1)
    
    #check if centroid similar word includes user input 
    for user_input in user_inputs:
        index = 0
        for (similar_word,_) in centroid_input1: #checking if similar word includes user input word
            if(user_input in similar_word):
                centroid_input1[index][0]=-1 #eliminate if similar word does 
            index+=1 #next input check
            
    for (similar_word,_) in centroid_input1:
        if similar_word !='-1':
            print(similar_word) #recommended word 
            break

    return c2_relevance,similar_word
