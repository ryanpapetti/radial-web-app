"""
utils.py

This script defines the relevant helper functions for main.py
"""

#Standard Python imports
import time, re, logging, random, requests, boto3, json
from botocore.errorfactory import ClientError

#Clustering imports
from scipy.cluster.hierarchy import cut_tree
from sklearn.cluster import KMeans

#Custom script imports
from scripts import SpotifyUser, Contacter


#Set random seed for reproducibility
random.seed(420)

#Logging formatter
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')






def createUserDataStructure(refresh_token, user_id, user_name):
    
    # create s3 client
    s3_client = boto3.client('s3')
    bucket = s3_client.get_object('radial-web-app-data')
    # check if user_id is already in the folder
    try:
        s3_client.head_object(Bucket='radial-web-app-data', Key=f'{user_id}/')
        # if it is, then check access token
        user_auth_info = s3_client.get_object(Bucket='radial-web-app-data', Key=f"{user_id}/auth.json")
    except ClientError:
        # User is Not found
        pass

    
    # if it isnt, make the folder and add info
    
    
    pass




def gatherAuthInfoAWS():
    secrets_client = boto3.client('secretsmanager')
    secret_info = secrets_client.get_secret_value(SecretId='radialspotifyauthcreds')
    secrets =  json.loads(secret_info['SecretString'])

    formatted_secrets = {}

    for secret in secrets:
        formatted_secrets[secret['Key']] = secret['Value']

    return formatted_secrets
        

# AUTH HASH HERE
AUTH_HASH = gatherAuthInfoAWS()['radial-spotify-auth-hash']



def refreshTheToken(refreshToken):
    """
    refreshTheToken(refreshToken)

    refreshToken - str

    Refreshes the user's access token with provided refresh token

    Returns access token and expiration to user in a dictionary
    """

    #Generate authorization hash and relevant data
    auth_header = {'Authorization': f'{AUTH_HASH}'}
    logging.info(f"REFRESHING THE TOKEN")
    data = {'grant_type': 'refresh_token', 'refresh_token': refreshToken}
    
    response = requests.post('https://accounts.spotify.com/api/token', data=data, headers=auth_header)

    spotifyToken = response.json()

    logging.info(spotifyToken)

    # Place the expiration time (current time + almost an hour), and access token into the json
    spotifyState = {'expiresAt': int(time.time()) + 3200, 'accessToken': spotifyToken['access_token']}
    return spotifyState


def gather_cluster_size_from_submission(submission):
    """
    gather_cluster_size_from_submission(submission)

    submission - str

    Parse the submission for cluster size and return the integer. It is guaranteed to be in here.

    Returns int of cluster size
    """
    pattern = r'\d+'
    return int(re.findall(pattern, submission)[0])



def prime_user_from_access_token(user_id,accessToken):
    """
    prime_user_from_access_token(user_id,accessToken)

    Create user instance and return

    Args:
        user_id (str)
        accessToken (str)

    Returns:
        SpotifyUser: instance to use for gathering etc.
    """
    user_contacter = Contacter()
    user_contacter.formAccessHeaderfromToken(accessToken)
    new_user = SpotifyUser(user_id, contacter=user_contacter)
    logging.info(f'user {user_id} has been primed from access token')
    return new_user


def prepare_data(user):
    """
    prepare_data(user)

    Gather and prepare all data for user. This will take a long time as it collects all track data for each user

    Args:
        user (SpotifyUser): must be made prior

    Returns:
        numpy array: normalized data to pass to clustering algorithm
    """

    #mostly logging for debugging purposes later. For around 2500 tracks it takes around 50s 
    logging.info('Timing how long data collection and storing takes')
    start_time = time.time()
    aggregated_audio_features = user.collect_data()
    logging.info(f'The elapsed time is {time.time() - start_time} seconds')
    user_prepped_data = user.prepare_data_for_clustering(aggregated_audio_features)

    normalized_data = SpotifyUser.normalize_prepped_data(user_prepped_data)
    return normalized_data



def execute_clustering(algorithm, clusters, normalized_data):
    """
    executes clustering with given algorithms, data, and clusters

    Args:
        algorithm (str): must be 'kmeans' or 'agglomerative hierarchical' when lowercased 
        clusters (int): number of clusters to pass to algorithm
        normalized_data (array-like): prepared and normalized data to cluster

    Raises:
        AssertionError: if the algorithm passed is not valid; this will be deprecated soon 

    Returns:
        DataFrame: labelled data after clustering
    """
    try:
        assert algorithm.lower() in ['kmeans', 'agglomerative hierarchical']
        labelled_data = normalized_data.copy()
        if algorithm.lower() == 'kmeans':
            model = KMeans(clusters)
            model.fit(normalized_data)
            cluster_labels = model.labels_
            labelled_data['Label'] = cluster_labels
        elif algorithm.lower() == 'agglomerative hierarchical':
            logging.info('Working with agglomerative hierarchical')
            linkage_matrix = SpotifyUser.produce_linkage_matrix(normalized_data)
            agglomerative_labels = cut_tree(linkage_matrix,clusters)
            labelled_data['Label'] = agglomerative_labels
        return labelled_data
    except AssertionError:
        raise AssertionError('Algorithm passed is NOT either kmeans or agglomerative hierarchical')




def prepare_playlists(user,labelled_data):
    """
    prepares the user's playlists for upload and display

    Args:
        user (SpotifyUser)
        labelled_data (DataFrame or array-like)

    Returns:
        Dictionary: uploadable playlists in JSON format
    """
    return user.generate_uploadable_playlists(labelled_data)


def get_cluster_playlist_metadata(clustered_tracks):
    """
    get the relevant metadata for the cluster for further organization

    Args:
        clustered_tracks (dict): cluster ids mapped to the tracks in their cluster

    Returns:
        Dictionary: JSON structure of cluster metadata
    """
    total_tracks = sum([len(tracks) for tracks in clustered_tracks.values()])
    total_organized_playlist_data = {}
    for playlist, tracks in clustered_tracks.items():
        logging.info(f'working with clustered playlist {playlist}')
        tracks_to_be_displayed = tracks[:5]
        centroid_track = tracks_to_be_displayed[0]
        playlist_size = len(tracks)
        playlist_proportion = round(100 * round(playlist_size/total_tracks, 3), 3)
        organized_playlist_data = {'centroid_track':centroid_track, 'displayable_tracks':tracks_to_be_displayed, 'all_tracks':tracks, 'size': format(playlist_size, ","), 'proportional_size': playlist_proportion}
        total_organized_playlist_data[playlist] = organized_playlist_data
    return total_organized_playlist_data


def get_displayable_tracks_metadata(authorization_header,track_ids):
    """
    get the relevant metadata for the tracks that will be displayed on the page

    Args:
        authorization_header (dict): valid authorization header
        track_ids (list): list of track_ids to get data for

    Returns:
        Dictionary: relevant tracks and their metadata in JSON format
    """
    track_ids_string = ','.join(track_ids)
    query_params = f'?ids={track_ids_string}'
    retrieved_metadata = requests.get(f'https://api.spotify.com/v1/tracks{query_params}', headers=authorization_header).json()

    total_track_metadata = []

    for track_data in retrieved_metadata['tracks']:
        # i just need the name and the album cover and url to play
        track_name = track_data['name']
        artists = ' / '.join([artist['name'] for artist in track_data['artists']])
        playable_url = track_data['external_urls']['spotify']
        album_cover_url = track_data['album']['images'][0]['url']
        track_metadata = {'name': track_name, 'playable_url':playable_url, 'album_cover_url':album_cover_url, 'artists':artists}
        total_track_metadata.append(track_metadata)
    
    return dict(zip(track_ids,total_track_metadata))


def organize_cluster_data_for_display(authorization_header,clustered_tracks):
    """
    collects and organizes relevant metadata to pass to templates for rendering

    Args:
        authorization_header (dict): valid authorization header
        clustered_tracks (dict): cluster IDs mapped to the tracks in their cluster

    Returns:
        tuple: displayable_data, total_organized_playlist_data to pass to HTML templates for rendering
    """
    total_organized_playlist_data = get_cluster_playlist_metadata(clustered_tracks)

    displayable_data = {}

    for playlist_id, data in total_organized_playlist_data.items():
        tracks_metadata = get_displayable_tracks_metadata(authorization_header, data['displayable_tracks'])
        displayable_data[playlist_id] = tracks_metadata
    
    return displayable_data, total_organized_playlist_data



# def get_deployed_cluster_obj(deployed_cluster_objs, cluster_id):
#     cluster_id = int(cluster_id) if type(cluster_id) == str else cluster_id
#     return deployed_cluster_objs[cluster_id]

# def load_proper_cluster_button(session,cluster_id):
#     logging.info(f'Passed cluster_id {cluster_id} ({type(cluster_id)})')
#     if 'DEPLOYED_CLUSTERS_OBJS' in session:
#         logging.info(f"DEPLOYED CLUSTERS ARE: {session['DEPLOYED_CLUSTERS_OBJS']} ")
#         logging.info(f"Cluster ID ({cluster_id}) and set of keys of objects ({set(session['DEPLOYED_CLUSTERS_OBJS'].keys())})")
#         if cluster_id in session['DEPLOYED_CLUSTERS_OBJS']:
#             return 'listen'
#     return 'deploy'
