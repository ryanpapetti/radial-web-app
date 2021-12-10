CREATE TABLE IF NOT EXISTS RadialUsers (
    SpotifyID varchar(255),
    DisplayName varchar(255),
    AccessToken varchar(255),
    RefreshToken varchar(255),
    AccessExpires int
);


CREATE TABLE IF NOT EXISTS Clusterings (
    ClusteringID varchar(255),
    SpotifyID varchar(255),
    ClusterAlgorithm varchar(255),
    ClustersChosen int
    
);

CREATE TABLE IF NOT EXISTS DeployedClusters (
    PlaylistID varchar(255),
    ClusteringID varchar(255),
    ClusterID varchar(255)
);