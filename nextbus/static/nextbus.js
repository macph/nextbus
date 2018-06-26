/*
Functions for list of stops.
*/

const INTERVAL = 60;
const REFRESH = true;
const STOPS_VISIBLE = 16;
const TILE_LIMIT = 128;
const TILE_ZOOM = 16;
const TIME_LIMIT = 60;

/**
 * Sets up element to activate geolocation and direct to correct page
 * @param {string} LocationURL URL to direct location requests to
 * @param {HTMLElement} activateElement Element to activate
 */
function addGeolocation(LocationURL, activateElement) {
    if (!navigator.geolocation) {
        console.log('Browser does not support geolocation.');
        return;
    }

    let success = function(position) {
        let latitude = position.coords.latitude.toFixed(6);
        let longitude = position.coords.longitude.toFixed(6);
        console.log('Current coordinates (' + latitude + ', ' + longitude + ')');
        // Direct to list of stops
        window.location.href = LocationURL + latitude + ',' + longitude;
    }
    let error = function(err) {
        console.log('Geolocation error: ' + err);
    }

    activateElement.addEventListener('click', function(event) {
        navigator.geolocation.getCurrentPosition(success, error);
    });
}


/**
 * Checks transition ending events to see which one is applicable, from Modernizr
 * @param {HTMLElement} element
 * @returns {string}
 */
function getTransitionEnd(element) {
    let transitions = {
        'transition': 'transitionend',
        'OTransition': 'oTransitionEnd',
        'MozTransition': 'transitionend',
        'WebkitTransition': 'webkitTransitionEnd'
    };
    for (let t in transitions) {
        if (transitions.hasOwnProperty(t) && element.style[t] !== undefined) {
        return transitions[t];
        }
    }
}

/**
 * Adds events for showing search bar for most pages
 */
function addSearchBarEvents() {
    let barHidden = true;
    let searchButton = document.getElementById('header-search-button');
    let searchButtonText = searchButton.querySelector('span');
    let searchBar = document.getElementById('header-search-bar');
    let searchBarInput = document.getElementById('search-form');
    let searchBarTransitionEnd = getTransitionEnd(searchBar)
    
    let transitionCallback = function() {
        searchBar.removeEventListener(searchBarTransitionEnd, transitionCallback);
        searchBarInput.focus();
    }
  
    let openSearchBar = function() {
        searchBar.classList.add('search-bar--open');
        searchButtonText.textContent = 'Close';
        searchButton.blur();
        barHidden = false;
        searchBar.addEventListener(searchBarTransitionEnd, transitionCallback);
    }
  
    let closeSearchBar = function() {
        searchBar.classList.remove('search-bar--open');
        searchButtonText.textContent = 'Search';
        searchBarInput.blur();
        barHidden = true;
    }
  
    searchButton.addEventListener('click', function() {
        if (barHidden) {
            openSearchBar();
        } else {
            closeSearchBar();
        }
    });
  
    document.addEventListener('click', function(event) {
        let bar = searchBar.contains(event.target);
        let button = searchButton.contains(event.target);
        if (!searchBar.contains(event.target) &&
            !searchButton.contains(event.target) &&
            !barHidden) {
            closeSearchBar();
        }
    });
}


/**
 * Resizes text within boxes
 * @param {...*} var_args Class names as args to modify text in
 */
function resizeIndicator() {
    for (let i = 0; i < arguments.length; i++) {
        let elements = document.getElementsByClassName(arguments[i]);
        for (let j = 0; j < elements.length; j++) {
            let elt = elements[j];
            let span = elt.querySelector('span');
            if (span !== null) {
                let ind = span.textContent;
                let len = ind.replace(/(&#?\w+;)/, ' ').length;
                switch (len) {
                case 1:
                    span.className = 'indicator__len1';
                    break;
                case 2:
                    // Text 'WW' is as wide as most 3-character strings
                    span.className = (ind === 'WW') ? 'indicator__len3' : 'indicator__len2';
                    break;
                case 3:
                    span.className = 'indicator__len3';
                    break;
                case 4:
                    span.className = 'indicator__len4';
                    break;
                default:
                    span.className = '';
                }
            } else {
                let img = elt.querySelector('img');
                if (typeof img === 'undefined') {
                    throw 'No span or image elements within stop indicator for element' + elt;
                }
                let style = window.getComputedStyle(elt);
                let fontSize = parseFloat(style.fontSize);
                img.width = Math.round(2.8 * fontSize);
            }
        }
    }
}


/**
 * Reverts colours of indicators
 * @param {...*} var_args Class names as arguments to revert colours
 */
function revertColours() {
    for (let i = 0; i < arguments.length; i++) {
        let elements = document.getElementsByClassName(arguments[i]);
        for (let j = 0; j < elements.length; j++) {
            let elt = elements[j];
            let style = window.getComputedStyle(elt);
            let foreground = style.getPropertyValue('color');
            let background = style.getPropertyValue('background-color');
            elt.style.backgroundColor = foreground;
            elt.style.color = background;
        }
    }
}

/**
 * Removes all subelements from an element
 * @param {HTMLElement} element Element to remove all children from
 */
function removeSubElements(element) {
    let last = element.lastChild;
    while (last) {
        element.removeChild(last);
        last = element.lastChild;
    }
}


/**
 * Retrieves live data and displays it in a table
 * @constructor
 * @param {string} atcoCode ATCO code for stop
 * @param {string} adminAreaCode Admin area code for stop, eg 099 for South Yorkshire
 * @param {string} table Table element in document
 * @param {string} time Element in document showing time when data was retrieved
 * @param {string} countdown Element in document showing time before next refresh
 */
function LiveData(atcoCode, adminAreaCode, table, time, countdown) {
    let self = this;
    this.atcoCode = atcoCode;
    this.adminAreaCode = adminAreaCode;
    this.url = LIVE_URL;
    this.table = table;
    this.headingTime = time;
    this.headingCountdown = countdown;
    this.countdownElement = null;
    this.data = null;

    this.interval = null;
    this.isLive = true;
    this.loopActive = false;
    this.loopEnding = false;

    /**
     * Gets data from server, refreshing table
     * @param {function} callback Callback to be used upon successful request
     */
    this.getData = function(callback) {
        self.headingTime.textContent = 'Updating...'
        let request = new XMLHttpRequest();
        request.open('GET', self.url + self.atcoCode, true);
        request.setRequestHeader('Content-Type', 'charset=utf-8');

        request.onreadystatechange = function() {
            if (request.readyState === XMLHttpRequest.DONE) {
                if (request.status === 200) {
                    console.log('Request for stop ' + self.atcoCode + ' successful');
                    self.data = JSON.parse(request.responseText);
                    self.isLive = true;
                    self.printData();
                } else if (self.data != null) {
                    self.isLive = false;
                    self.printData();
                } else {
                    self.isLive = false;
                    self.headingTime.textContent = 'No data available';
                }
                if (typeof callback !== 'undefined') {
                    callback(self.atcoCode);
                }
            }
        }

        request.send();
    };

    /**
     * Draws table from data
     */
    this.printData = function() {
        let clLive;
        if (self.isLive) {
            clLive = 'service--live';
        } else {
            self.updateOutdatedData();
            clLive = 'service--estimated';
        }

        let container = document.getElementById(self.table);
        let heading = document.getElementById(self.headingTime);

        /**
         * Prints remaining seconds as 'due' or 'x min'
         * @param {number} sec Remaining seconds
         */
        let strDue = function(sec) {
            let due = Math.round(sec / 60);
            let str = (due < 2) ? 'due' : due + ' min';
            return str;
        }

        if (self.data !== null && self.data.services.length > 0) {
            if (self.isLive) {
                heading.textContent = 'Live times at ' + self.data.local_time;
            } else {
                heading.textContent = 'Estimated times from ' + self.data.local_time;
            }

            let table = document.createElement('div');
            table.className = 'list-services';
            for (let s = 0; s < self.data.services.length; s++) {
                let service = self.data.services[s];
                let row = s + 1;

                // Cell showing bus line number
                let cNum = document.createElement('div');
                cNum.className = 'service service__line';
                cNum.style.msGridRow = row;

                // Inner div to center line number and size properly
                let cNumInner = document.createElement('div');
                cNumInner.className = 'service service__line__inner area-' + self.adminAreaCode;
                if (service.name.length > 6) {
                    cNumInner.classList.add('service__line--small');
                }
                let cNumInnerSpan = document.createElement('span');
                cNumInnerSpan.appendChild(document.createTextNode(service.name));
                cNumInner.appendChild(cNumInnerSpan);
                cNum.appendChild(cNumInner);

                // Destination
                let cDest = document.createElement('div');
                cDest.className = 'service service__destination';
                cDest.style.msGridRow = row;
                let cDestSpan = document.createElement('span');
                cDestSpan.appendChild(document.createTextNode(service.dest));
                cDest.appendChild(cDestSpan);

                // Next bus due
                let cNext = document.createElement('div');
                cNext.className = 'service service__next';
                cNext.style.msGridRow = row;
                let cNextSpan = document.createElement('span');
                if (service.expected[0].live) {
                    cNextSpan.className = clLive;
                }
                let exp = strDue(service.expected[0].secs)
                cNextSpan.appendChild(document.createTextNode(exp));
                cNext.appendChild(cNextSpan);

                // Buses after
                let cAfter = document.createElement('div');
                cAfter.className = 'service service__after';
                cAfter.style.msGridRow = row;
                let cAfterSpan = document.createElement('span');

                // If number of expected services is 2, only need to show the 2nd service here
                if (service.expected.length == 2) {
                    let firstMin = document.createElement('span');
                    if (service.expected[1].live) {
                        firstMin.className = clLive;
                    }
                    firstMin.appendChild(
                        document.createTextNode(strDue(service.expected[1].secs))
                    );
                    cAfter.appendChild(firstMin);

                // Otherwise, show the 2nd and 3rd services
                } else if (service.expected.length > 2) {
                    let firstMin = document.createElement('span');
                    if (service.expected[1].live) {
                        firstMin.className = clLive;
                    }
                    let secondMin = document.createElement('span');
                    if (service.expected[2].live) {
                        secondMin.className = clLive;
                    }
                    let exp1 = strDue(service.expected[1].secs).replace('min', 'and');
                    firstMin.appendChild(document.createTextNode(exp1));
                    let exp2 = strDue(service.expected[2].secs)
                    secondMin.appendChild(document.createTextNode(exp2));

                    cAfterSpan.appendChild(firstMin);
                    cAfterSpan.appendChild(document.createTextNode(' '));
                    cAfterSpan.appendChild(secondMin);
                }
                cAfter.appendChild(cAfterSpan);

                // Add the four cells to new table
                table.appendChild(cNum);
                table.appendChild(cDest);
                table.appendChild(cNext);
                table.appendChild(cAfter);
            }
            // Remove all existing elements
            removeSubElements(container);
            // Add table
            container.appendChild(table);
            console.log('Created table with ' + self.data.services.length +
                        ' services for stop "' + self.atcoCode + '".');

        } else if (self.data !== null) {
            removeSubElements(container);
            if (self.isLive) {
                heading.textContent = 'No services expected at ' + self.data.local_time;
            } else {
                heading.textContent = 'No services found';
            }
            console.log('No services found for stop ' + self.atcoCode + '.');
        } else {
            heading.textContent = 'Updating...';
            console.log('No data received yet when printed for stop ' + self.atcoCode);
        }
    };

    /**
     * Updates seconds remaining with current date/time if no data received
     */
    this.updateOutdatedData = function() {
        let dtNow = new Date();
        // Loop backwards while removing services to avoid skipping other services
        let i = self.data.services.length;
        while (i--) {
            let s = self.data.services[i];
            let j = s.expected.length;
            while (j--) {
                let e = s.expected[j];
                let dtExp = new Date(e.exp_date);
                e.secs = Math.round((dtExp - dtNow) / 1000);
                if (e.secs < 0) {
                    // Remove services past their expected datetime
                    s.expected.splice(j, 1);
                }
            }
            if (s.expected.length === 0) {
                let index = self.data.services.indexOf(s);
                self.data.services.splice(index, 1);
            }
        }
        // Sort by time remaining on first service coming
        self.data.services.sort(function(a, b) {
            return a.expected[0].secs - b.expected[0].secs;
        });
        let dtReq = new Date(self.data.iso_date);
        let overDue = Math.round((dtNow - dtReq) / 60000);
        console.log('Live data overdue ' + overDue + ' minutes.');
    };

    /**
     * Starts up the class with interval for refreshing. If it is already active, the table and
     * countdown are set to the correct elements again.
     * @param {Object} callbacks Callback functions called at start, within interval or at end
     * @param {function} callbacks.onStart At start of loop, when data is received.
     *     If not defined the onInter function is called instead
     * @param {function} callbacks.onInter Called every interval after initial interval
     * @param {function} callbacks.onEnd Called when interval finishes and loop stops
     */
    this.startLoop = function(callbacks) {
        let onInter, onStart, onEnd;
        if (typeof callbacks !== 'undefined') {
            onInter = callbacks.onInter;
            onStart = (typeof callbacks.onStart !== 'undefined') ? callbacks.onStart : onInter;
            onEnd = callbacks.onEnd;
        }

        self.countdownElement = document.getElementById(self.headingCountdown);
        if (self.loopActive) {
            if (self.loopEnding) {
                self.loopEnding = false;
            }
            if (typeof onStart !== 'undefined') {
                onStart(self.atcoCode);
            }
            self.printData();
            return;
        }

        self.getData(onStart);
        if (REFRESH) {
            self.loopActive = true;
            let time = INTERVAL;
            self.interval = setInterval(function() {
                time--;
                self.countdownElement.textContent = (time > 0) ? time + 's' : 'now';
                if (time <= 0) {
                    if (self.loopEnding) {
                        self.loopActive = false;
                        self.loopEnding = false;
                        clearInterval(self.interval);
                        if (typeof onEnd !== 'undefined') {
                            onEnd(self.atcoCode);
                        }
                    } else {
                        self.getData(onInter);
                        time = INTERVAL;
                    }
                }
            }, 1000);
        } else {
            self.countdownElement.textContent.textContent = '';
        }
    };

    /**
     * Sets the loop to not repeat after it runs out. Can be restarted with startLoop() again
     * @param {function} callback - Calls function at same time
     */
    this.stopLoop = function(callback) {
        if (self.loopActive) {
            self.loopEnding = true;
        }
        if (typeof callback !== 'undefined') {
            callback(self.atcoCode);
        }
    };
}


/**
 * Creates a map element using Leaflet.js and returns it.
 * @param {string} mapToken Map token for access to Mapbox's maps
 * @param {string} mapElement Empty div element to be used for map
 * @param {Object} stops Either a single stop or a list of stops in GeoJSON format
 * @param {function} callback Optional callback function when clicking on a marker
 */
function addMap(token, mapElement, stops, callback) {
    let layer = L.tileLayer(
        'https://api.tiles.mapbox.com/v4/{id}/{z}/{x}/{y}.png?access_token={accessToken}',
        {
            attribution: 'Map data &copy; <a href="http://openstreetmap.org">OpenStreetMap</a> ' +
                'contributors, <a href="http://creativecommons.org/licenses/by-sa/2.0/">CC-BY-SA' +
                '</a>, Imagery © <a href="http://mapbox.com">Mapbox</a>',
            maxZoom: 18,
            id: 'mapbox.emerald',
            accessToken: token
        }
    )

    let stopsGeo = new L.GeoJSON(stops, {
        pointToLayer: function(point, latLng) {
            let ind;
            if (point.properties.indicator !== '') {
                ind = '<span>' + point.properties.indicator + '</span>'
            } else {
                let src = (point.properties.stopType === 'PLT') ? TRAM_SVG : BUS_SVG;
                let alt = (point.properties.stopType === 'PLT') ? 'Tram stop' : 'Bus stop';
                ind = '<img src="' + src + '" width=28px alt="' + alt + '">'
            }

            let area = 'area-' + point.properties.adminAreaRef;

            let bearing;
            if (point.properties.bearing !== null) {
                let arrow = 'indicator-marker__arrow--' + point.properties.bearing;
                bearing = '<div class="indicator-marker__arrow ' + arrow + '"></div>'
            } else {
                bearing = '';
            }

            let innerHTML = '<div class="indicator indicator-marker ' + area + '">' +
                bearing + ind + '</div>';

            let icon = L.divIcon({
                className: 'marker',
                iconSize: null,
                html: innerHTML
            });
            let marker = L.marker(
                latLng,
                {
                    icon: icon,
                    title: point.properties.title,
                    alt: point.properties.indicator
                }
            );
            // Move marker to front when mousing over
            marker = marker.on('mouseover', function(event) {
                this.setZIndexOffset(1000);
            });
            // Move marker to original z offset when mousing out
            marker = marker.on('mouseout', function(event) {
                this.setZIndexOffset(0);
            });
            // Add callback function to each marker with GeoJSON pointer object as argument
            if (typeof callback !== 'undefined') {
                marker = marker.on('click', function(event) {
                    callback(point)
                });
            }

            return marker;
        }
    });
    let bounds = stopsGeo.getBounds();

    let map = L.map(mapElement, {
        center: bounds.getCenter(),
        zoom: 18,
        minZoom: 9,
        maxBounds: L.latLngBounds(
            L.latLng(49.5, -9.0),
            L.latLng(61.0, 2.5)
        )
    });

    layer.addTo(map);
    stopsGeo.addTo(map);
    map.fitBounds(bounds, {padding: [24, 24]});

    return map;
}


/**
 * Stores tile layers in object and array such that properties are stored in order and dropped if
 * the max limit is exceeded
 * @constructor
 * @param {number} max Max size of array before properties start being dropped
 * @param {function} canDelete Function to check if the first entry can be removed. If not defined,
 *    the first entry is always removed when the array is full.
 */
function TileCache(max, canDelete) {
    let self = this;
    this.max = max;
    this.canDelete = canDelete;
    this._obj = new Object();
    this._array = new Array();

    /**
     * Size of array
     */
    this.size = function() {
        return Object.keys(self._obj).length
    }

    /**
     * Gets object property by key and pushes it to front
     * @param {string} key Object key
     */
    this.get = function(key) {
        if (self._obj.hasOwnProperty(key)) {
            let index = self._array.indexOf(key);
            if (index !== self.size() - 1) {
                self._array.splice(self._array.indexOf(key), 1);
                self._array.push(key);
            }
            return self._obj[key];
        } else {
            return null;
        }
    }

    /**
     * Gets object property but does not change its order
     * @param {string} key Object key
     */
    this.select = function(key) {
        return (self._obj.hasOwnProperty(key)) ? self._obj[key] : null;
    }

    /**
     * Adds entry to array with key and value. If the array is already at maximum size, the first
     * property is ejected
     * @param {string} key Object key
     * @param {Object} value Object property
     */
    this.add = function(key, value) {
        self._obj[key] = value;
        self._array.push(key)

        if (self.size() <= self.max) {
            return;
        }

        if (typeof self.check === 'undefined') {
            let first = self._array.shift();
            delete self._obj[first];
            return;
        }

        for (let i = 0; i < self._array.length; i++) {
            let key = self._array[i];
            if (self.canDelete(self._obj[key])) {
                let remove = self._array.splice(i, 1);
                delete self._obj[remove];
                break;
            }
        }
    }

    /**
     * Checks if key exists
     * @param {string} key Object key
     */
    this.has = function(key) {
        return self._obj.hasOwnProperty(key);
    }

    /**
     * Returns array of keys held by object
     */
    this.keys = function() {
        return Object.keys(self._obj);
    }

    /**
     * Iterates over all properties in array
     * @param {function} func Function on each property in object
     */
    this.forEach = function(func) {
        for (let key in self._obj) {
            if (self._obj.hasOwnProperty(key)) {
                func(self._obj[key]);
            }
        }
    }
}


/**
 * Detect IE use so can disable arrows - CSS transformations do not work properly
 * Credit: https://stackoverflow.com/a/21712356
 */
function detectIE() {
    let ua = window.navigator.userAgent;
    return (ua.indexOf('MSIE ') > -1 || ua.indexOf('Trident/') > -1);
}


/**
 * Handles layers of stop markers
 * @constructor
 * @param {Object} stopMap Parent stop map object
 * @param {function} callback Function for each marker when clicked
 */
function StopLayer(stopMap, callback) {
    let self = this;
    this.stopMap = stopMap;
    this.callback = callback;
    this.isIE = detectIE();

    this.currentStop = null;
    this.loadedStops = new TileCache(TILE_LIMIT, function(layer) {
        return (!self.stopMap.hasLayer(layer));
    });

    /**
     * Get index to be used with list of stop tiles
     * @param {Object} coords Coordinates returned from tile event
     */
    this.getIndex = function(coords) {
        return 'x' + coords.x + 'y' + coords.y;
    }

    /**
     * Loads tile with stops - if it doesn't exist in cache, download data
     * @param {Object} coords Tile coordinates at level TILE_ZOOM
     */
    this.loadTile = function(coords) {
        let index = self.getIndex(coords);
        if (self.loadedStops.has(index)) {
            let stops = self.loadedStops.get(index);
            if (stops !== null) {
                stops.addTo(self.stopMap.map);
                resizeIndicator('indicator-marker');
            }
            return;
        }

        let url = TILE_URL + '?x=' + coords.x + '&y=' + coords.y;
        let request = new XMLHttpRequest;
        request.open('GET', url, true);
        request.addEventListener('load', function() {
            let data = JSON.parse(this.responseText);
            if (data.features.length > 0) {
                self.loadedStops.add(index, self.createLayer(data));
                self.loadedStops.get(index).addTo(self.stopMap.map);
                resizeIndicator('indicator-marker');
            } else {
                self.loadedStops.add(index, null);
            }
        });
        request.send();
    }

    /**
     * Removes all tiles - but data stays in cache
     */
    this.removeAllTiles = function() {
        self.stopMap.map.eachLayer(function(layer) {
            if (!(layer instanceof L.TileLayer)) {
                self.stopMap.map.removeLayer(layer);
            }
        });
    }

    /**
     * Gets coordinates of all tiles visible current map at level TILE_ZOOM
     */
    this._getTileCoordinates = function() {
        let pixelScale = self.stopMap.layer.getTileSize();
        let bounds = self.stopMap.map.getBounds();

        let getTile = function(coords) {
            let absolute = self.stopMap.map.project(coords, TILE_ZOOM)
            return absolute.unscaleBy(pixelScale).floor();
        }
        let northwest = getTile(bounds.getNorthWest());
        let southeast = getTile(bounds.getSouthEast());

        let tileCoords = [];
        for (let i = northwest.x; i <= southeast.x; i++) {
            for (let j = northwest.y; j <= southeast.y; j++) {
                tileCoords.push({x: i, y: j});
            }
        }

        return tileCoords;
    }

    /**
     * Updates all stop point tiles, removing hidden tiles and adding new tiles
     */
    this.updateTiles = function() {
        if (self.stopMap.map.getZoom() < STOPS_VISIBLE) {
            return;
        }

        let tiles = self._getTileCoordinates();
        let tileIndices = tiles.map(self.getIndex);
        let keys = self.loadedStops.keys();

        for (let i = 0; i < keys.length; i++) {
            let key = keys[i];
            let index = tileIndices.indexOf(key);
            if (index > -1) {
                self.loadTile(tiles[index]);
                tiles.splice(index, 1);
                tileIndices.splice(index, 1);
            } else {
                let layer = self.loadedStops.select(key);
                if (self.stopMap.map.hasLayer(layer)) {
                    self.stopMap.map.removeLayer(layer);
                }
            }
        }

        /* Add all remaining tiles not in cache */
        for (let i = 0; i < tiles.length; i++) {
            self.loadTile(tiles[i]);
        }
    }

    /**
     * Creates marker element to be used in map
     * @param {Object} point Point object from data
     */
    this.markerElement = function(point) {
        let ind = '';
                if (point.properties.indicator !== '') {
                    ind = '<span>' + point.properties.indicator + '</span>'
                } else if (point.properties.stopType === 'BCS' ||
                            point.properties.stopType === 'BCT') {
                    ind = '<img src="' + BUS_SVG + '" width=28px>'
                } else if (point.properties.stopType === 'PLT') {
                    ind = '<img src="' + TRAM_SVG + '" width=28px>'
                }

        let arrow = '';
                if (!self.isIE) {
                    let bearing = 'indicator-marker__arrow--' + point.properties.bearing;
                    arrow = '<div class="indicator-marker__arrow ' + bearing + '"></div>';
                }

                let area = 'area-' + point.properties.adminAreaRef;
        let indClass = 'indicator indicator-marker ' + area;
        let innerHTML = '<div class="' + indClass + '">' + arrow + ind + '</div>';

        return innerHTML;
    }

    /**
     * Creates GeoJSON layer of stops from list of stops
     * @param {Object} stops FeatureCollection data of stops within title
     */
    this.createLayer = function(stops) {
        let stopLayer = new L.GeoJSON(stops, {
            pointToLayer: function(point, latLng) {
                let icon = L.divIcon({
                    className: 'marker',
                    iconSize: null,
                    html: self.markerElement(point)
                });
                let marker = L.marker(latLng, {
                        icon: icon,
                        title: point.properties.title,
                        alt: point.properties.indicator
                });
                // Move marker to front when mousing over
                marker = marker.on('mouseover', function(event) {
                    this.setZIndexOffset(1000);
                });
                // Move marker to original z offset when mousing out
                marker = marker.on('mouseout', function(event) {
                    this.setZIndexOffset(0);
                });
                // Add callback function to each marker with GeoJSON pointer object as argument
                if (typeof self.callback !== 'undefined') {
                    marker = marker.on('click', function(event) {
                        self.callback(point)
                    });
                }

                return marker;
            }
        });

        return stopLayer;
    };
}


/**
 * Handles the stop panel
 * @param {Object} stopMap Parent stop map object
 * @param {HTMLElement} mapPanel Panel HTML element
 */
function StopPanel(stopMap, mapPanel) {
    let self = this;
    this.stopMap = stopMap
    this.mapPanel = mapPanel;
    this.activeStops = new Object();
    this.currentStop = null;

    /**
     * Gets index for list of stops
     * @param {string} atcoCode
     */
    this.getIndex = function(atcoCode) {
        return 's' + atcoCode;
    }

    /**
     * Gets live data object for a bus stop or create one if it does not exist
     * @param {string} atcoCode ATCO code for bus stop
     * @param {string} adminAreaRef Admin area code for bus stop
     * @param {string} table Table element ID
     * @param {string} time Heading element ID
     * @param {string} countdown Countdown element ID
     */
    this.getStop = function(atcoCode, adminAreaRef, table, time, countdown) {
        let index = self.getIndex(atcoCode);
        if (!self.activeStops.hasOwnProperty(index)) {
            self.activeStops[index] = new LiveData(
                atcoCode,
                adminAreaRef,
                table,
                time,
                countdown
            );
        }
        self.stopAllLoops(atcoCode);
        self.activeStops[index].startLoop({
            onEnd: function(atcoCode) {
                if (self.activeStops.hasOwnProperty(index)) {
                    delete self.activeStops[index];
                }
            }
        });
        return self.activeStops[index];
    }

    /**
     * Stops all loops
     * @param {string} exceptCode ATCO code for bus stop to be excluded
     */
    this.stopAllLoops = function(exceptCode) {
        let exceptIndex = (typeof exceptCode !== 'undefined') ? self.getIndex(exceptCode): null;
        for (let index in self.activeStops) {
            let valid = self.activeStops.hasOwnProperty(index);
            if (valid && index !== exceptIndex) {
                self.activeStops[index].stopLoop();
            }
        }
    }

    /**
     * Clears all subelements from panel
     */
    this.clearPanel = function() {
        while (self.mapPanel.firstChild) {
            self.mapPanel.removeChild(self.mapPanel.firstChild);
        }
    }

    /**
     * Sets message when zoom level too small
     */
    this._setPanelOutOfZoom = function() {
        let heading = document.createElement('div');
        heading.className = 'heading heading--panel';
        let headingText = document.createElement('h2');
        headingText.textContent = 'Zoom in to see stops';
        heading.appendChild(headingText);

        self.clearPanel();
        self.mapPanel.appendChild(heading);
    }


    /**
     * Sets message when zoom level right
     */
    this._setPanelInZoom = function() {
        let heading = document.createElement('div');
        heading.className = 'heading heading--panel';
        let headingText = document.createElement('h2');
        headingText.textContent = 'Select a stop';
        heading.appendChild(headingText);

        self.clearPanel();
        self.mapPanel.appendChild(heading);
    }


    /**
     * Sets panel for bus stop live data and other associated info
     * @param {Object} point GeoJSON data for stop point
     */
    this._setStopPanel = function(point) {
        self.currentStop = point.properties.atcoCode;
        self.stopMap.setURL();

        let heading = document.createElement('div');
        heading.className = 'heading-stop';

        let stopInd = document.createElement('div');
        stopInd.className = 'indicator area-' + point.properties.adminAreaRef;
        let ind = null;
        if (point.properties.indicator !== '') {
            ind = document.createElement('span');
            ind.textContent = point.properties.indicator;
        } else if (point.properties.stopType === 'BCS' ||
                    point.properties.stopType === 'BCT') {
            ind = document.createElement('img');
            ind.src = BUS_SVG;
            ind.width = '28';
            ind.alt = 'Bus stop';
        } else if (point.properties.stopType === 'PLT') {
            ind = document.createElement('img');
            ind.src = TRAM_SVG;
            ind.width = '28';
            ind.alt = 'Tram stop';
        }
        stopInd.appendChild(ind);
        let stopHeading = document.createElement('h1');
        stopHeading.textContent = point.properties.name;
        heading.appendChild(stopInd);
        heading.appendChild(stopHeading);

        let headingOuter = document.createElement('div');
        headingOuter.className = 'heading heading--panel';
        headingOuter.id = 'panel-heading-outer';
        headingOuter.appendChild(heading);
        if (point.properties.bearing !== null) {
            let headingText = document.createElement('p');
            if (point.properties.street !== null) {
                headingText.innerHTML = '<strong>' + point.properties.street + '</strong>, ' +
                    point.properties.bearing + '-bound';
            } else {
                headingText.textContent = point.properties.bearing + '-bound';
            }
            headingOuter.appendChild(headingText);
        }

        let liveTimes = document.createElement('section');
        liveTimes.className = 'card card--panel';
        let liveHeading = document.createElement('div');
        liveHeading.className = 'heading-inline heading-inline--right';
        let liveHeadingTime = document.createElement('h2');
        liveHeadingTime.id = 'live-time';
        liveHeadingTime.textContent = 'Retrieving live data...';
        let liveHeadingCountdown = document.createElement('p');
        liveHeadingCountdown.id = 'live-countdown';
        liveHeading.appendChild(liveHeadingTime);
        liveHeading.appendChild(liveHeadingCountdown);
        let liveServices = document.createElement('div');
        liveServices.id = 'services';
        liveTimes.appendChild(liveHeading);
        liveTimes.appendChild(liveServices);

        let stopInfo = document.createElement('section');
        stopInfo.className = 'card card--panel';
        let infoHeading = document.createElement('h2');
        infoHeading.textContent = 'Stop information';
        let smsCode = document.createElement('p');
        smsCode.innerHTML = 'SMS code <strong>' + point.properties.naptanCode+ '</strong>';
        stopInfo.appendChild(infoHeading);
        stopInfo.appendChild(smsCode);

        self.clearPanel();
        self.mapPanel.appendChild(headingOuter);
        resizeIndicator('indicator');
        self.mapPanel.appendChild(liveTimes);
        self.mapPanel.appendChild(stopInfo);

        let activeStop = self.getStop(
            point.properties.atcoCode,
            point.properties.adminAreaRef,
            'services',
            'live-time',
            'live-countdown'
        );
    }

    /**
     * Sets panel depending on existence of point data and zoom level
     * @param {Object} point If not null, displays stop point live data/info
     * @param {number} zoom Set message depending on zoom level
     */
    self.setPanel = function(point, zoom) {
        if (point !== null) {
            self._setStopPanel(point);
        } else if (self.currentStop === null) {
            if (zoom < STOPS_VISIBLE) {
                self._setPanelOutOfZoom();
            } else {
                self._setPanelInZoom();
            }
        }
    }
}


/**
 * Handles the map container and stops
 * @param {string} mapToken Mapbox token
 * @param {string} mapContainer ID for map container element
 * @param {string} mapPanel ID for map panel element
 */
function StopMap(mapToken, mapContainer, mapPanel) {
    let self = this;
    this.mapContainer = document.getElementById(mapContainer);
    this.mapPanel = document.getElementById(mapPanel);

    this.map = null;
    this.layer = L.tileLayer(
        'https://api.tiles.mapbox.com/v4/{id}/{z}/{x}/{y}.png?access_token={accessToken}',
        {
            minZoom: 9,
            maxZoom: 18,
            id: 'mapbox.emerald',
            accessToken: mapToken
        }
    )

    this.panel = new StopPanel(this, this.mapPanel);
    this.stops = new StopLayer(this, this.panel.setPanel);

    /**
     * Starts up the map and adds map events
     * @param {Object} point GeoJSON for initial stop point
     * @param {number} latitude Starts map at centre with latitude if point not defined
     * @param {number} longitude Starts map at centre with longitude if point not defined
     * @param {number} zoom Starts map at centre with zoom level if point not defined
     */
    this.init = function(point, latitude, longitude, zoom) {
        let coords, zoomLevel;
        if (latitude && longitude && zoom) {
            coords = L.latLng(latitude, longitude);
            zoomLevel = zoom;
        } else if (point !== null) {
            coords = L.latLng(point.geometry.coordinates[1], point.geometry.coordinates[0]);
            zoomLevel = 17;
        } else {
            throw 'Arguments passed to StopMap.init() not valid';
        }

        self.map = L.map(self.mapContainer.id, {
            zoom: zoomLevel,
            center: coords,
            minZoom: 9,
            maxZoom: 18,
            maxBounds: L.latLngBounds(
                L.latLng(49.5, -9.0),
                L.latLng(61.0, 2.5)
            ),
            attributionControl: false
        });

        self.map.on('zoomend', function(event) {
            if (self.map.getZoom() < STOPS_VISIBLE) {
                self.stops.removeAllTiles();
            } else {
                self.stops.updateTiles();
            }
            self.setURL();
            self.panel.setPanel(null, self.map.getZoom());
        });
    
        self.map.on('moveend', function(event) {
            self.setURL();
            self.stops.updateTiles();
        });

        self.map.on('click', function(event) {
            self.panel.currentStop = null;
            self.panel.setPanel(null, self.map.getZoom());
        });

        self.layer.addTo(self.map);
        self.stops.updateTiles();
        self.panel.setPanel(point, zoomLevel);
    }

    /**
     * Sets page to new URL with current stop, coordinates and zoom
     */
    this.setURL = function() {
        let center = self.map.getCenter();
        let zoom = self.map.getZoom();

        let stop = self.panel.currentStop;
        let coords = center.lat + ',' + center.lng + ',' + zoom;
        let newURL = (stop !== null) ? MAP_URL + stop + '/' + coords : MAP_URL + coords;

        history.replaceState(null, null, newURL);
    }
}
