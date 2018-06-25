/*
Functions for list of stops.
*/

const INTERVAL = 60;
const REFRESH = true;
const TIME_LIMIT = 60;

/**
 * Sets up element to activate geolocation and direct to correct page
 * @param {string} LocationURL URL to direct location requests to
 * @param {HTMLElement} activateElement Element to activate
 * @param {HTMLElement} errorElement Optional element to display message in case it does not work
 */
function addGeolocation(LocationURL, activateElement, errorElement) {
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
        if (typeof errorElement !== 'undefined') {
            output.textContent = 'Unable to retrieve your location. ' +
                'Try searching with a postcode.';
        }
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
 * @param {string} url URL to send requests to
 * @param {Element} tableElement Table element in document
 * @param {Element} timeElement Element in document showing time when data was retrieved
 * @param {Element} countdownElement Element in document showing time before next refresh
 */
function LiveData(atcoCode, adminAreaCode, url, tableElement, timeElement, countdownElement) {
    let self = this;
    this.atcoCode = atcoCode;
    this.adminAreaCode = adminAreaCode;
    this.url = url;
    this.table = tableElement;
    this.headingTime = timeElement;
    this.headingCountdown = countdownElement;
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
        console.log('Sending request to ' + self.url + ' with code="' +
                    self.atcoCode + '"');
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
                    callback();
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

        /**
         * Prints remaining seconds as 'due' or 'x min'
         * @param {number} sec Remaining seconds
         */
        let strDue = function(sec) {
            let due = Math.round(sec / 60);
            let str = (due < 2) ? 'due' : due + ' min';
            return str;
        }

        if (self.data.services.length > 0) {
            if (self.isLive) {
                self.headingTime.textContent = 'Live times at ' + self.data.local_time;
            } else {
                self.headingTime.textContent = 'Estimated times from ' + self.data.local_time;
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
            removeSubElements(self.table);
            // Add table
            self.table.appendChild(table);
            console.log('Created table with ' + self.data.services.length +
                        ' services for stop "' + self.atcoCode + '".');

        } else {
            // Remove all existing elements if they exist
            removeSubElements(self.table);
            if (self.isLive) {
                self.headingTime.textContent = 'No services expected at ' + self.data.local_time;
            } else {
                self.headingTime.textContent = 'No services found';
            }
            console.log('No services found for stop ' + self.atcoCode + '.');
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
     * Starts up the class with interval for refreshing
     * @param {function} callbackInter Function to be used when data comes in each interval.
     *     The getData() function already checks if this function is defined before calling
     * @param {function} callbackStart Function to be used when data comes in for the first time.
     *     If this argument is undefined, the callbackInter function is used instead
     */
    this.startLoop = function(callbackInter, callbackStart) {
        let onInterval = callbackInter;
        let onStart = (typeof callbackStart !== 'undefined') ? callbackStart : callbackInter;
        if (self.loopActive) {
            if (self.loopEnding) {
                self.loopEnding = false;
            }
            if (typeof onStart !== 'undefined') {
                onStart();
            }
            return;
        } else {
            self.getData(onStart);
        }
        if (REFRESH) {
            self.loopActive = true;
            let time = INTERVAL;
            self.interval = setInterval(function () {
                time--;
                self.headingCountdown.textContent = (time > 0) ? time + 's' : 'now';
                if (time <= 0) {
                    if (self.loopEnding) {
                        self.loopActive = false;
                        self.loopEnding = false;
                        clearInterval(self.interval);
                    } else {
                        self.getData(onInterval);
                        time = INTERVAL;
                    }
                }
            }, 1000);
        } else {
            self.headingCountdown.textContent = '';
        }
    };

    /**
     * Stops the interval, leaving it paused. Can be restarted with startLoop() again
     * @param {function} callback - Calls function at same time
     */
    this.stopLoop = function(callback) {
        if (self.loopActive) {
            self.loopEnding = true;
        }
        if (typeof callback !== 'undefined') {
            callback();
        }
    };
}


/**
 * Creates a map element using Leaflet.js and returns it.
 * @param {HTMLElement} mapElement Empty div element to be used for map
 * @param {string} token Map token for access to Mapbox's maps
 * @param {JSON} stops Either a single stop or a list of stops in GeoJSON format
 * @param {string} busSVG Link to SVG source for bus icon
 * @param {string} tramSVG Link to SVG source for tram icon
 * @param {function} callback Optional callback function when clicking on a marker
 */
function addMap(mapElement, token, stops, busSVG, tramSVG, callback) {
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
                let src = (point.properties.stopType === 'PLT') ? tramSVG : busSVG;
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

    let map = L.map(mapElement.id, {
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
 * Detect IE use so can disable arrows - CSS transformations do not work properly
 * Credit: https://stackoverflow.com/a/21712356
 */
function detectIE() {
    let ua = window.navigator.userAgent;
    return (ua.indexOf('MSIE ') > -1 || ua.indexOf('Trident/') > -1);
}


function StopLayer(map, panel, callback) {
    let self = this;
    this.STOPS_VISIBLE = 16;
    this.map = map;
    this.panel = panel;
    this.callback = callback;
    this.isIE = detectIE();

    this.currentStop = null;
    this.loadedStops = new Object();

    this.getIndex = function(coords) {
        return 'x' + coords.x + 'y' + coords.y + 'z' + coords.z;
    }

    this.loadTile = function(coords) {
        if (coords.z < self.STOPS_VISIBLE) {
            return;
        }
        let url = TILE_URL + '?x=' + coords.x + '&y=' + coords.y + '&z=' + coords.z;
        let index = self.getIndex(coords);

        let request = new XMLHttpRequest;
        request.open('GET', url, true);
        request.addEventListener('load', function() {
            let data = JSON.parse(this.responseText);

            if (data.features.length > 0) {
                self.loadedStops[index] = self.createLayer(data);
                self.loadedStops[index].addTo(self.map);
                resizeIndicator('indicator-marker');
            }
        });
        request.send();
    }

    this.removeTile = function(coords) {
        let index = self.getIndex(coords);
        if (typeof self.loadedStops[index] !== 'undefined') {
            self.loadedStops[index].clearLayers();
            self.map.removeLayer(self.loadedStops[index]);
            delete self.loadedStops[index];
        }
    }

    this.removeAll = function(coords) {
        for (let index in self.loadedStops) {
            if (self.loadedStops.hasOwnProperty(index)) {
                self.loadedStops[index].clearLayers();
                self.map.removeLayer(self.loadedStops[index]);
                delete self.loadedStops[index];
            }
        }
    }

    this.createLayer = function(stops) {
        let stopLayer = new L.GeoJSON(stops, {
            pointToLayer: function(point, latLng) {
                let ind;
                if (point.properties.indicator !== '') {
                    ind = '<span>' + point.properties.indicator + '</span>'
                } else if (point.properties.stopType === 'BCS' ||
                            point.properties.stopType === 'BCT') {
                    ind = '<img src="' + BUS + '" width=28px>'
                } else if (point.properties.stopType === 'PLT') {
                    ind = '<img src="' + TRAM + '" width=28px>'
                } else {
                    ind = '';
                }

                let arrow;
                if (!self.isIE) {
                    let bearing = 'indicator-marker__arrow--' + point.properties.bearing;
                    arrow = '<div class="indicator-marker__arrow ' + bearing + '"></div>';
                } else {
                    arrow = '';
                }

                let area = 'area-' + point.properties.adminAreaRef;
                let innerHTML = '<div class="indicator indicator-marker ' + area + '">' +
                    arrow + ind + '</div>';

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


function StopPanel(map, mapPanel) {
    let self = this;
    this.map = map;
    this.mapPanel = mapPanel;
}


function StopMap(mapToken, mapContainer, mapPanel) {
    let self = this;
    this.mapContainer = mapContainer;
    this.mapPanel = mapPanel;

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

    this.panel = new StopPanel(self.map, self.mapPanel);
    this.stops = new StopLayer(self.map, self.panel);

    this.init = function(latitude, longitude, zoom) {
        self.map = L.map(self.mapContainer.id, {
            zoom: zoom,
            center: L.latLng(latitude, longitude),
            minZoom: 9,
            maxZoom: 18,
            maxBounds: L.latLngBounds(
                L.latLng(49.5, -9.0),
                L.latLng(61.0, 2.5)
            ),
            attributionControl: false
        });

        self.panel.map = self.map;
        self.stops.map = self.map;

        self.map.on('zoomstart', function(event) {
            if (self.map.getZoom() < self.stops.STOPS_VISIBLE) {
                self.stops.removeAll();
            }
        })

        self.map.on('zoomend', function(event) {
            self.setURL();
        });
    
        self.map.on('moveend', function(event) {
            self.setURL();
        });

        self.layer.on('tileload', function(tile) {
            self.stops.loadTile(tile.coords);
        })

        self.layer.on('tileunload', function(tile) {
            self.stops.removeTile(tile.coords);
        })

        self.layer.addTo(self.map);
    }

    this.setURL = function() {
        let center = self.map.getCenter();
        let zoom = self.map.getZoom();
        let newURL = MAP_URL + center.lat + ',' + center.lng + ',' + zoom;

        history.replaceState(null, null, newURL);
    }
}
