let funfacts = ["Did you know Radial organizes your playlists so that the closest song to the centroid is first?",
"The idea for Radial was born in 2018 and began as a clustering exploration project.",
"Radial gets its name from how tracks are organized in the playlist; the closer the song is to the top, the smaller its radius!",
"Radial uses all open-source software and was built in Flask, SQLite, and other Python scripts on top of an Nginx server.",
"Want to make improvements? Check out our GitHub or DockerHub.",
"Clustering is an example of unsupervised machine learning, where the model does not know the target values of the original data.",
"Many AI apps stray away from clustering because there is no mathematically optimal answer - it's up to you!",
"Ryan Papetti created Radial as his Graduate Capstone for the University of Arizona in Fall 2021.",
"Thanks for waiting! You should be proud of yourself today - and everyday!"];



function shuffleArray(array) {
    for (var i = array.length - 1; i > 0; i--) {
    
        // Generate random number
        var j = Math.floor(Math.random() * (i + 1));
                    
        var temp = array[i];
        array[i] = array[j];
        array[j] = temp;
    }
        
    return array;
    }
    


function newQuote() {
    var shuffledArray = shuffleArray(funfacts);
    var quote1 = shuffledArray.pop();
    var quote2 = shuffledArray.pop();
    document.getElementById('quote1Display').innerHTML = quote1;
    document.getElementById('quote2Display').innerHTML = quote2;
}