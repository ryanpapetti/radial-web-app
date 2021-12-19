'''
Radial Web App
main.py
This script runs the Flask application and performs all routing tasks
'''


#Standard Python imports
import json, random, uuid, sqlite3, time, os, shutil, requests

#Flask imports
from flask import Flask, request, redirect, render_template, url_for
from flask.helpers import make_response
from urllib.parse import quote

#Explicit function imports from utils.py file 
from utils import prime_user_from_access_token, prepare_playlists, prepare_data, execute_clustering, gather_cluster_size_from_submission, organize_cluster_data_for_display, refreshTheToken





#Creating initial Flask app and setting random seed for strict initialization
app = Flask(__name__)
random.seed(420)


#Custom DEBUG mode to make it simpler to run locally or on server. If True, app runs on local port. Use False only for production
DEBUG_MODE = False

if DEBUG_MODE:
    # Server-side Parameters
    CLIENT_SIDE_URL = "http://127.0.0.1"
    PORT = 8095
    REDIRECT_URI = "{}:{}/callback".format(CLIENT_SIDE_URL,PORT)
    SCHEME='http'
else:
    CLIENT_SIDE_URL = "https://radial-app.com"
    REDIRECT_URI = "{}/callback".format(CLIENT_SIDE_URL)
    SCHEME='https'

#Former session code that will be kept for future 
# app.config["SESSION_PERMANENT"] = False
# app.config['SESSION_TYPE'] = 'filesystem'
# app.secret_key = str(uuid.uuid4())
# Session(app)

#Initialize contact to database
DATABASE = 'app_data/basic_user_credentials.db'
DB_CREATION_SCRIPT = 'app_data/create_radial_tables.sql'
USER_DATA_PATH = 'app_data/user_data'


def get_db():
    """
    get_db()

    Connects to the global DATABASE file

    Returns:
        sqlite3 connection
    """
    db = sqlite3.connect(DATABASE)
    return db


def init_db():
    """
    init_db()

    Formally initializes the database and REMOVES IT  if it already exists.
    If it does not exist, it creates it from the DB_CREATION_SCRIPT global variable


    Returns None

    """
    with app.app_context():
        if os.path.exists(DATABASE):
            os.remove(DATABASE)
        db = get_db()
        with app.open_resource(DB_CREATION_SCRIPT, mode='r') as f:
            db.cursor().executescript(f.read())
        db.commit()

#formally initialize database
init_db()


def close_connection(db):
    db.close()

# Client Keys - these need to be changed prior to non-beta production
CLIENT_ID = "7ec4038de1184e2fb0a1caf13352e295"
CLIENT_SECRET = '18fa59e0d4614c139f4c6102f5bc965a'

# Spotify URLS
SPOTIFY_AUTH_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_API_BASE_URL = "https://api.spotify.com"
API_VERSION = "v1"
SPOTIFY_API_URL = "{}/{}".format(SPOTIFY_API_BASE_URL, API_VERSION)


#Scopes for Web App - must be in this format
SCOPE = "user-read-recently-played user-top-read  playlist-modify-public playlist-modify-private user-library-modify playlist-read-private user-read-email user-read-private user-library-read playlist-read-collaborative"


#specific query parameters prior to authentication
auth_query_parameters = {
    "response_type": "code",
    "redirect_uri": REDIRECT_URI,
    "scope": SCOPE,
    "client_id": CLIENT_ID,
    "show_dialog":'true'
}




#################################### BELOW ARE FLASK ROUTES ####################################



@app.route("/")
def index():
    """
    index()

    Render the homepage.html template
    """
    return render_template('homepage.html')

@app.route("/appeducation")
def appeducation():
    """
    appeducation()

    Gather the spotify user id from the request and render the appeducation.html template
    """    
    spotify_user_id = request.args.get('spotify_user_id')
    return render_template('appeducation.html', spotify_user_id = spotify_user_id)


@app.route("/authenticateuser")
def authenticateuser():
    """
    authenticateuser()

    Redirect the user to the Spotify Authorization URL for the application 
    """
    # Auth Step 1: Authorization
    url_args = "&".join(["{}={}".format(key, quote(val)) for key, val in auth_query_parameters.items()])
    auth_url = "{}/?{}".format(SPOTIFY_AUTH_URL, url_args)
    return redirect(auth_url)


@app.route("/callback")
def callback():
    """
    callback()

    Creates the appropriate data structures for the user and redirects them to the appeducation page
    """
    # Request refresh and access tokens

    auth_token = request.args['code']
    code_payload = {
        "grant_type": "authorization_code",
        "code": str(auth_token),
        "redirect_uri": REDIRECT_URI,
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET
    }

    #logging payload for debugging
    app.logger.info(msg=code_payload)

    #Post request for access and refresh tokens
    post_request = requests.post(SPOTIFY_TOKEN_URL, data=code_payload)
    
    # Retrieve and log releveant data
    response_data = json.loads(post_request.text)
    app.logger.info(f"{response_data}")
    access_token = response_data["access_token"]
    refresh_token = response_data["refresh_token"]
    # token_type = response_data["token_type"]
    expires_in = response_data["expires_in"]


    # The application should now have access to access tokens. Use it to gather the bare minimum user data to initialize

    # Create authorization header
    authorization_header = {"Authorization": "Bearer {}".format(access_token), 'Content-Type': 'application/x-www-form-urlencoded'}

    # Get user profile data
    user_profile_api_endpoint = "{}/me".format(SPOTIFY_API_URL)
    profile_response = requests.get(user_profile_api_endpoint, headers=authorization_header)
    profile_data = json.loads(profile_response.text)
    user_id = profile_data['id']
    user_display_name = profile_data['display_name']


    #Creating data structures for user

    #Make cursor for database 
    db_connection = get_db()
    cursor = db_connection.cursor()

    #Gather all SpotifyIDs in database to determine initialization process with user 
    all_data = cursor.execute("SELECT SpotifyID FROM RadialUsers;").fetchall()
    verify_prior_entry = (user_id,) in all_data
    app.logger.info(f"User already in DB: {verify_prior_entry} ({all_data})")

    #if the user is already in the database
    if verify_prior_entry:
        #now check if the access token is expired - if it is then we need to refresh it
        user_data = cursor.execute(f'SELECT * FROM RadialUsers WHERE SpotifyID="{user_id}" ORDER BY AccessExpires DESC;').fetchone()
        recorded_expiration = user_data[-1]

        #if the access token IS expired, refresh it 
        if time.time() > int(recorded_expiration):
            #refresh token
            refresh_token_data = refreshTheToken(refresh_token)
            access_token = refresh_token_data['accessToken']
            expires_in = refresh_token_data['expiresAt']

        #Update user with new data regardless
        replace_statement = f'UPDATE RadialUsers SET RefreshToken=?, AccessExpires=? WHERE SpotifyId="{user_id}";'
        replaceable_values = (refresh_token, expires_in + int(time.time()))
        # app.logger.info(f"updating with these values to db {replaceable_values}")
        cursor.execute(replace_statement, replaceable_values)
    

    #if the user is BRAND NEW, add them to the database
    else:
        app.logger.info('BRAND NEW USER ADDING TO DB')
        insert_statement = 'INSERT INTO RadialUsers(SpotifyId,DisplayName,AccessToken,RefreshToken,AccessExpires) VALUES(?,?,?,?,?);'
        insertable_values = (user_id,user_display_name,access_token, refresh_token, expires_in)
        cursor.execute(insert_statement, insertable_values)
    
    db_connection.commit()
    cursor.close()

    #create temporary user flat file structures 

    #remove flat file path if it already exists
    if user_id in os.listdir(f"{USER_DATA_PATH}"):
       shutil.rmtree(f"{USER_DATA_PATH}/{user_id}")

    #make the user's data path
    os.mkdir(f"{USER_DATA_PATH}/{user_id}")

    #log statement to confirm execution of function
    app.logger.info(msg='Set user')

    #redirect to appeducation
    proper_url = url_for('appeducation', spotify_user_id = user_id, _scheme=SCHEME, _external=True)
    return redirect(proper_url)


@app.route('/loadingpage', methods=['POST'])
def loadingpage():
    """
    loadingpage()

    This accepts the original POST request to cluster data and renders a loadingpage that supposed to display until clustering is done. The loadingpage file has independent JQuery and Javascript that control this rerouting.  
    """

    #Gather relevant GET and POST data
    spotify_user_id = request.args.get('spotify_user_id')
    algorithm = request.form.get('algorithm')
    desired_clusters = request.form.get('desired_clusters')
    chosen_algorithm = algorithm

    #extract cluster size using custom function
    chosen_clusters = gather_cluster_size_from_submission(desired_clusters)
    
    #this logic is temporary and will be moved, but checks if the chosen_clusters created is valid or not since ther would be occasional errors where the wrong cluster size gets extracted
    if chosen_clusters not in [5,9,13]:
        raise AssertionError('THE PASSSED CLUSTER SIZE IS INVALID')
    
    #render the loadingpage.html templaet
    return render_template('loadingpage.html', spotify_user_id = spotify_user_id, chosen_clusters = chosen_clusters, chosen_algorithm = chosen_algorithm)



@app.route('/clustertracks', methods=['POST'])
def clustertracks():
    """
    clustertracks()

    Handles the logic of clustering the user's tracks. This function takes a long time and runs in the background while loadingpage() entertains the users. Returns a successful 200 response if data posts 
    """

    #Gather appropriate data
    spotify_user_id = request.args.get('spotify_user_id')
    chosen_algorithm = request.form.get('chosen_algorithm')
    chosen_clusters = int(request.form.get('chosen_clusters'))
    
    #Perform temporary validation that will be soon deprecated
    if chosen_clusters not in [5,9,13]:
        raise AssertionError(f'THE PASSSED CLUSTER SIZE IS INVALID: {chosen_clusters}')


    #Retrieve relevant user data to create obj
    retrieved_id, retrieved_display_name, retrieved_access_token = get_db().cursor().execute(f'SELECT * FROM RadialUsers WHERE SpotifyID="{spotify_user_id}";').fetchone()[:3]

    app.logger.info(f"gathered the following from the db: {retrieved_id} vs {spotify_user_id}, {retrieved_display_name}, {retrieved_access_token}")
    
    # assert spotify_user_id == retrieved_id

    #Create the user object from the access token 
    user_obj = prime_user_from_access_token(spotify_user_id, retrieved_access_token)
    

    #Begin gathering user clustering data
    app.logger.info(msg='Gathering entirety of user track library and preparing for clustering')
    user_prepared_data = prepare_data(user_obj)

    #Temporarily store in a CSV file for debugging purposes
    user_prepared_data.to_csv(f'app_data/user_data/{retrieved_id}/user_prepared_data.csv')

    app.logger.info(msg='Data successfully gathered and prepared')

    #Execute clustering of user track data with given parameters
    app.logger.info(f'PREPARING TO CLUSTER DATA WITH {chosen_algorithm} {chosen_clusters}')

    labelled_data = execute_clustering(chosen_algorithm,chosen_clusters,user_prepared_data)
    
    #Temporarily store for debugging purposes
    labelled_data.to_csv(f'app_data/user_data/{retrieved_id}/labelled_data.csv')
    app.logger.info(msg='Data clustered')


    #Finally, prepare the user playlists for rendering and display
    prepared_playlists = prepare_playlists(user_obj,labelled_data)
    with open(f'app_data/user_data/{retrieved_id}/prepared_playlists.json','w') as writer:
        json.dump(prepared_playlists,writer)
    app.logger.info(msg='Dumped user cluster results to JSON')

    #Insert clustering parameters for statistical purposes 
    insert_statement = 'INSERT INTO Clusterings(ClusteringID,SpotifyID,ClusterAlgorithm,ClustersChosen) VALUES(?,?, ?, ?)'
    insertable_values = (str(uuid.uuid4()), retrieved_id, chosen_algorithm,chosen_clusters)
    db_connection = get_db()
    cursor = db_connection.cursor()
    cursor.execute(insert_statement, insertable_values)
    db_connection.commit()
    cursor.close()


    #Create final response to indicate successful clustering

    return make_response('SUCCESSFULLY CLUSTERED AND STORED RELEVANT DATA', 200)






@app.route("/clusteringresults")
def clusteringresults():
    """
    clusteringresults()

    Display the results of clustering to the user
    """

    #Gather relevant data
    app.logger.info(f"{request.args}")
    spotify_user_id = request.args.get('spotify_user_id')
    with open(f'{USER_DATA_PATH}/{spotify_user_id}/prepared_playlists.json') as reader:
        prepared_playlists = json.load(reader) 
    chosen_clusters = int(request.args.get('chosen_clusters' if 'chosen_clusters' in request.args else 'amp;chosen_clusters'))
    chosen_algorithm = request.args.get('chosen_algorithm' if 'chosen_algorithm' in request.args else 'amp;chosen_algorithm')
    retrieved_id, retrieved_display_name, retrieved_access_token = get_db().cursor().execute(f'SELECT * FROM RadialUsers WHERE SpotifyID="{spotify_user_id}"').fetchone()[:3]
    #Establish authorization header for posting to Spotify
    auth_header = {'Authorization': f'Bearer {retrieved_access_token}'}

    #Retrieve relevant displayable data for clustering results and save
    displayable_data, total_organized_playlist_data = organize_cluster_data_for_display(auth_header,prepared_playlists)

    with open(f'app_data/user_data/{retrieved_id}/total_organized_playlist_data.json','w') as writer:
        json.dump(total_organized_playlist_data,writer)

    # render the clusteringresults page with passed data
    return render_template("clusteringresults.html", displayable_data = displayable_data, total_organized_playlist_data = total_organized_playlist_data, chosen_algorithm = chosen_algorithm, chosen_clusters = chosen_clusters, spotify_user_id = spotify_user_id)


@app.route("/clusteringresults#<cluster_id>")
def deploy_cluster(cluster_id):
    """
    deploy_cluster(cluster_id)

    Deploy's a user's cluster to Spotify identified by cluster_id 

    Redirects to created playlist on Spotify in new tab 
    """

    #Log relevant data for debugging purposes
    app.logger.info(f"cluster id passed: {cluster_id}")
    app.logger.info(f"get params: {request.args.keys()}")
    app.logger.info(f"get params values: {list(request.args.values())}")
    

    #Gathering relevant data to post
    spotify_user_id = request.args.get('spotify_user_id')
    with open(f'{USER_DATA_PATH}/{spotify_user_id}/total_organized_playlist_data.json') as reader:
        total_organized_playlist_data = json.load(reader) 
    
    #weird ampsersand issues that require special parsing
    chosen_algorithm = request.args.get('chosen_algorithm' if 'chosen_algorithm' in request.args else 'amp;chosen_algorithm')
    chosen_clusters = int(request.args.get('chosen_clusters' if 'chosen_clusters' in request.args else 'amp;chosen_clusters'))

    #Retrieve relevant data
    retrieved_id, retrieved_display_name, retrieved_access_token = get_db().cursor().execute(f'SELECT * FROM RadialUsers WHERE SpotifyID="{spotify_user_id}";').fetchone()[:3]

    #Logging for debugging
    app.logger.info(f"gathered the following from the db: {retrieved_id}, {retrieved_display_name}, {retrieved_access_token}")

    #Create user obj to post playlist to Spotify
    specified_user = prime_user_from_access_token(retrieved_id, retrieved_access_token)
    specified_user.optional_display_id = retrieved_display_name

    #Logging for debugging
    app.logger.info(f'{total_organized_playlist_data.keys()}')
    
    #Retrieve the tracks for the user's passed cluster_id regardless of format
    try:
        tracks_to_add = total_organized_playlist_data[int(cluster_id)]['all_tracks']
    
    except KeyError:
        tracks_to_add = total_organized_playlist_data[cluster_id]['all_tracks']
    
    #Preparing data for deploying the cluster
    specified_algorithm = chosen_algorithm
    specified_clusters = chosen_clusters
    clustering_type = f"{specified_algorithm.title()} ({specified_clusters})"

    #Deploy the cluster
    playlist_obj = specified_user.deploy_single_cluster_playlist(tracks_to_add, int(cluster_id) + 1, clustering_type)
    playlist_url = f'https://open.spotify.com/playlist/{playlist_obj.playlist_id}'

    #Redirect to playlist URL
    return redirect(playlist_url)
    



#RUN THE FLASK SCRIPT EITHER LOCALLY OR ON SERVER
if __name__ == "__main__":
    if DEBUG_MODE:
        app.run(debug=True, port=PORT)
    else:
        app.run(host = '0.0.0.0')
        import sys; sys.exit(0)
