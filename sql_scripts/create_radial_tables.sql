
USE radial_app;

CREATE TABLE IF NOT EXISTS RadialUsers (
    SpotifyID varchar(255) PRIMARY KEY,
    DisplayName varchar(255),
    AccessToken varchar(511),
    RefreshToken varchar(511),
    AccessExpires int
);


CREATE TABLE IF NOT EXISTS Clusterings (
    ClusteringID varchar(255) PRIMARY KEY,
    SpotifyID varchar(255),
    ClusterAlgorithm varchar(255),
    ClustersChosen int
    
);

CREATE TABLE IF NOT EXISTS DeployedClusters (
    PlaylistID varchar(255) PRIMARY KEY,
    ClusteringID varchar(255),
    ClusterID varchar(255)
);