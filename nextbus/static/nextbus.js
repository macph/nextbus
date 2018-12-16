/*
 * nextbus website functionality, copyright Ewan Macpherson 2017-18
 */

const INTERVAL = 60;

const MAP_ZOOM_MIN = 7;
const MAP_ZOOM_MAX = 18;
const MAP_CENTRE_GB = [54.00366, -2.547855];
const MAP_BOUNDS_NW = [61, 2];
const MAP_BOUNDS_SE = [49, -8];

const TILE_LIMIT = 64;
const TILE_ZOOM = 15;

const LAYOUT_SPACE_X = 30;
const LAYOUT_CURVE_MARGIN = 6;
const LAYOUT_LINE_STROKE = 7.2;
const LAYOUT_INVISIBLE = 'rgba(255, 255, 255, 0)';
const LAYOUT_TIMEOUT = 500;

const LAYOUT_DOM_TEXT_START = 12;
const LAYOUT_DOM_DIV_START = 15;
const LAYOUT_DOM_PARA_START = 36 + 12;


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
    };
    let error = function(err) {
        console.log('Geolocation error: ' + err);
    };

    activateElement.addEventListener('click', function() {
        navigator.geolocation.getCurrentPosition(success, error);
    });
}


/**
 * Sends requests to modify cookie data with list of starred stops
 * @constructor
 * @param {boolean} cookieSet Whether cookie has been set in first place or not
 * @param {HTMLElement} info Info element to show for setting cookie data
 */
function StarredStops(cookieSet, info) {
    let self = this;
    this.set = (typeof cookieSet !== 'undefined') ? cookieSet : true;
    this.info = info;
    this.data = null;
    this.active = false;
    this.r = new XMLHttpRequest();

    this._confirm = function(element, code) {
        let resizeInfo = function() {
            self.info.style.height = 'auto';
            self.info.style.height = self.info.scrollHeight + 'px';
        };
        self.info.style.height = self.info.scrollHeight + 'px';
        window.addEventListener('resize', resizeInfo);
    
        element.blur();
        element.textContent = 'Confirm starred stop';
        element.onclick = function() {
            self.set = true;
            self.add(element, code, function() {
                self.info.style.height = 0 + 'px';
                window.removeEventListener('resize', resizeInfo);
            });
        };
    };

    this.get = function(callback) {
        self.r.onload = function() {
            let newData = JSON.parse(this.responseText);
            self.data = newData.stops;
            callback();
        };
        self.r.open("GET", STARRED_URL, true);
        self.r.send();
    };

    this.add = function(element, code, callback) {
        if (!self.set) {
            self._confirm(element, code);
            return;
        }
        if (self.active) {
            return;
        }
        self.r.onload = function() {
            self.active = false;
            element.blur();
            element.onclick = function(event) {
                self.remove(event.target, code);
            };
            element.textContent = 'Remove starred stop';
            if (typeof callback !== 'undefined') {
                callback();
            }
        };
        self.r.open("POST", STARRED_URL + code, true);
        self.r.setRequestHeader('Content-type', 'application/x-www-form-urlencoded');
        self.r.send();
    };

    this.remove = function(element, code, callback) {
        if (self.active || !self.set) {
            return;
        }
        self.r.onload = function() {
            self.active = false;
            element.blur();
            element.onclick = function(event) {
                self.add(event.target, code);
            };
            element.textContent = 'Add starred stop';
            if (typeof callback !== 'undefined') {
                callback();
            }
        };
        self.r.open("DELETE", STARRED_URL + code, true);
        self.r.setRequestHeader('Content-type', 'application/x-www-form-urlencoded');
        self.r.send();
    };
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
    let searchBarTransitionEnd = getTransitionEnd(searchBar);

    let transitionCallback = function() {
        searchBar.removeEventListener(searchBarTransitionEnd, transitionCallback);
        searchBarInput.focus();
    };

    let openSearchBar = function() {
        searchBar.classList.add('search-bar--open');
        searchButtonText.textContent = 'Close';
        searchButton.blur();
        barHidden = false;
        searchBar.addEventListener(searchBarTransitionEnd, transitionCallback);
    };

    let closeSearchBar = function() {
        searchBar.classList.remove('search-bar--open');
        searchButtonText.textContent = 'Search';
        searchBarInput.blur();
        barHidden = true;
    };

    searchButton.addEventListener('click', function() {
        if (barHidden) {
            openSearchBar();
        } else {
            closeSearchBar();
        }
    });

    document.addEventListener('click', function(event) {
        if (event.target instanceof HTMLElement &&
            !searchBar.contains(event.target) &&
            !searchButton.contains(event.target) &&
            !barHidden)
        {
            closeSearchBar();
        }
    });
}


/**
 * Resize text within boxes
 * @param {...*} classes Class names as args to modify text in
 */
function resizeIndicator(...classes) {
    for (let i = 0; i < classes.length; i++) {
        let elements = document.getElementsByClassName(classes[i]);
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
 * @param {...*} classes Class names as arguments to revert colours
 */
function revertColours(...classes) {
    for (let i = 0; i < classes.length; i++) {
        let elements = document.getElementsByClassName(classes[i]);
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
 * Removes all sub-elements from an element
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
 * JSON data from API for live bus times data.
 * @typedef {{
 *     atcoCode: string,
 *     naptanCode: string,
 *     isoDate: string,
 *     localTime: string,
 *     services: {
 *         line: string,
 *         name: string,
 *         dest: string,
 *         opName: string,
 *         opCode: string,
 *         expected: {
 *             live: boolean,
 *             secs: number,
 *             expDate: string
 *         }[]
 *     }[]
 * }} LiveTimesData
 */


/**
 * Retrieves live data and displays it in a table
 * @constructor
 * @param {string} atcoCode ATCO code for stop
 * @param {string} adminAreaCode Admin area code for stop, eg 099 for South Yorkshire
 * @param {(HTMLElement|string)} table Table element or ID in document
 * @param {(HTMLElement|string)} time Element or ID in document showing time when data was
 * retrieved
 * @param {(HTMLElement|string)} countdown Element or ID in document showing time before next
 * refresh
 */
function LiveData(atcoCode, adminAreaCode, table, time, countdown) {
    let self = this;
    this.atcoCode = atcoCode;
    this.adminAreaCode = adminAreaCode;
    this.url = LIVE_URL;

    this.table = (table instanceof HTMLElement) ? table : document.getElementById(table);
    this.headingTime = (time instanceof HTMLElement) ? time : document.getElementById(time);
    this.headingCountdown = (countdown instanceof HTMLElement) ?
        countdown : document.getElementById(countdown);

    /**
     * Live time data from API.
     * @type {?LiveTimesData}
     */
    this.data = null;

    this.interval = null;
    this.isLive = true;
    this.loopActive = false;
    this.loopEnding = false;

    /**
     * Called after live data is successfully received.
     * @callback afterLiveData
     * @param {string} atcoCode
     */

    /**
     * Gets data from server, refreshing table
     * @param {afterLiveData} [after] Callback to be used upon successful request
     */
    this.getData = function(after) {
        self.headingTime.textContent = 'Updating...';
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
                if (typeof after !== 'undefined') {
                    after(self.atcoCode);
                }
            }
        };

        request.send();
    };

    /**
     * Prints remaining seconds as 'due' or 'x min'
     * @param {number} sec Remaining seconds
     * @private
     */
    this._strDue = function(sec) {
        let due = Math.round(sec / 60);
        return (due < 2) ? 'due' : due + ' min';
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

        if (self.data !== null && self.data.services.length > 0) {
            if (self.isLive) {
                self.headingTime.textContent = 'Live times at ' + self.data.localTime;
            } else {
                self.headingTime.textContent = 'Estimated times from ' + self.data.localTime;
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
                let exp = self._strDue(service.expected[0].secs);
                cNextSpan.appendChild(document.createTextNode(exp));
                cNext.appendChild(cNextSpan);

                // Buses after
                let cAfter = document.createElement('div');
                cAfter.className = 'service service__after';
                cAfter.style.msGridRow = row;
                let cAfterSpan = document.createElement('span');

                // If number of expected services is 2, only need to show the 2nd service here
                if (service.expected.length === 2) {
                    let firstMin = document.createElement('span');
                    if (service.expected[1].live) {
                        firstMin.className = clLive;
                    }
                    firstMin.appendChild(
                        document.createTextNode(self._strDue(service.expected[1].secs))
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
                    let exp1 = self._strDue(service.expected[1].secs).replace('min', 'and');
                    firstMin.appendChild(document.createTextNode(exp1));
                    let exp2 = self._strDue(service.expected[2].secs);
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

        } else if (self.data !== null) {
            removeSubElements(self.table);
            if (self.isLive) {
                self.headingTime.textContent = 'No services expected at ' + self.data.localTime;
            } else {
                self.headingTime.textContent = 'No services found';
            }
            console.log('No services found for stop ' + self.atcoCode + '.');
        } else {
            self.headingTime.textContent = 'Updating...';
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
                let dtExp = new Date(e.expDate);
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
        let dtReq = new Date(self.data.isoDate);
        let overDue = Math.round((dtNow - dtReq) / 60000);
        console.log('Live data overdue ' + overDue + ' minutes.');
    };

    /**
     * Called on start, every interval or when the loop ends.
     * @callback callbackLiveData
     * @param {string} atcoCode
     */

    /**
     * Starts up the class with interval for refreshing. If it is already active, the table and
     * countdown are set to the correct elements again.
     * @param {object} [callbacks] Callback functions called at start, within interval or at end
     * @param {callbackLiveData} [callbacks.start] At start of loop, when data is received.
     * If not defined the onInter function is called instead
     * @param {callbackLiveData} [callbacks.interval] Called every interval after initial interval
     * @param {callbackLiveData} [callbacks.end] Called when interval finishes and loop stops
     */
    this.startLoop = function(callbacks) {
        let onInter, onStart, onEnd;
        if (typeof callbacks !== 'undefined') {
            onInter = callbacks.interval;
            onStart = (typeof callbacks.start !== 'undefined') ? callbacks.start : onInter;
            onEnd = callbacks.end;
        }

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

        let time = INTERVAL;
        self.loopActive = true;
        self.interval = setInterval(function() {
            time--;
            self.headingCountdown.textContent = (time > 0) ? time + 's' : 'now';
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
    };

    /**
     * Sets the loop to not repeat after it runs out. Can be restarted with startLoop() again
     * @param {callbackLiveData} callback - Calls function at same time
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
 * Stores tile layers in map such that keys are stored in order and dropped if the max limit is
 * exceeded
 * @constructor
 * @param {number} max Max size of array before properties start being dropped
 */
function TileCache(max) {
    let self = this;
    this.max = max;
    this._data = new Map();

    Object.defineProperty(this, 'size', {
        get: function() {
            return this._data.size;
        }
    });

    /**
     * Create hash with Cantor pairing function
     * @param {{x: number, y: number}} coords
     */
    this.hash = function(coords) {
        return 0.5 * (coords.x + coords.y) * (coords.x + coords.y + 1) + coords.y;
    };

    /**
     * Gets value from map by key and push to front if requested
     * @param {{x: number, y: number}} coords
     * @param {boolean} push Push key/value to front
     */
    this.get = function(coords, push) {
        let key = self.hash(coords);
        let obj = self._data.get(key);
        if (typeof obj === 'undefined') {
            return;
        }
        if (push) {
            self._data.delete(key);
            self._data.set(key, obj);
        }
        return obj.layer;
    };

    /**
     * Adds coordinates and layer to map, keeping to maximum size
     * @param {{x: number, y: number}} coords
     * @param {object} layer Leaflet Layer object
     */
    this.set = function(coords, layer) {
        self._data.set(self.hash(coords), {coords: coords, layer: layer});
        if (self._data.size > self.max) {
            let first = null;
            self._data.forEach(function(layer, key) {
                if (first === null) {
                    first = key;
                }
            });
            self._data.delete(first);
        }
    };

    /**
     * Checks if coordinates exist in map
     * @param {{x: number, y: number}} coords
     * @returns {boolean}
     */
    this.has = function(coords) {
        return self._data.has(self.hash(coords));
    };

    /**
     * Returns array of coordinates within map
     * @returns {{x: number, y: number}[]}
     */
    this.coords = function() {
        let array = [];
        self._data.forEach(function(obj) {
            array.push(obj.coords);
        });

        return array;
    };

    /**
     * Iterates over each entry in map, with function accepting layer and coordinates objects
     */
    this.forEach = function(func) {
        self._data.forEach(function(obj) {
            func(obj.layer, obj.coords);
        });
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
 * GeoJSON data for a stop point
 * @typedef {{
 *     type: string,
 *     geometry: {
 *         type: string,
 *         coordinates: number[]
 *     },
 *     properties: {
 *         atcoCode: string,
 *         naptanCode: string,
 *         title: string,
 *         name: string
 *         indicator: string,
 *         street: string,
 *         bearing: string,
 *         stopType: string,
 *         adminAreaRef: string
 *     }
 * }} StopPoint
 */


/**
 * Handles layers of stop markers
 * @constructor
 * @param {object} stopMap Parent stop map object
 */
function StopLayer(stopMap) {
    let self = this;
    this.stopMap = stopMap;
    this.zCount = 0;
    this.isIE = detectIE();
    this.loadedStops = new TileCache(TILE_LIMIT);
    self.layers = L.layerGroup();

    /**
     * Sets up layer group.
     */
    this.init = function() {
        self.layers.addTo(self.stopMap.map);
    };

    /**
     * Loads tile with stops - if it doesn't exist in cache, download data
     * @param {object} coords Tile coordinates at level TILE_ZOOM
     */
    this.loadTile = function(coords) {
        let layer = self.loadedStops.get(coords, true);
        if (typeof layer !== 'undefined') {
            if (layer !== null) {
                self.layers.addLayer(layer);
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
                self.loadedStops.set(coords, self.createLayer(data));
                self.layers.addLayer(self.loadedStops.get(coords));
                resizeIndicator('indicator-marker');
            } else {
                self.loadedStops.set(coords, null);
            }
        });

        request.send();
    };

    /**
     * Removes all tiles - but data stays in cache
     */
    this.removeAllTiles = function() {
        self.layers.eachLayer(function(layer) {
            self.layers.removeLayer(layer);
        });
    };

    /**
     * Converts latitude longitude coordinates to grid coordinates at TILE_ZOOM
     * @param {L.Point} scale
     * @param {L.latLng} coords
     */
    this._getTileCoords = function(scale, coords) {
        let absolute = self.stopMap.map.project(coords, TILE_ZOOM);
        return absolute.unscaleBy(scale).floor();
    };

    /**
     * Gets coordinates of all tiles visible current map at level TILE_ZOOM
     */
    this._getTileCoordinates = function() {
        let pixelScale = self.stopMap.tileLayer.getTileSize(),
            bounds = self.stopMap.map.getBounds();

        let northwest = self._getTileCoords(pixelScale, bounds.getNorthWest()),
            southeast = self._getTileCoords(pixelScale, bounds.getSouthEast());

        let tileCoords = [];
        for (let i = northwest.x; i <= southeast.x; i++) {
            for (let j = northwest.y; j <= southeast.y; j++) {
                tileCoords.push({x: i, y: j});
            }
        }

        return tileCoords;
    };

    /**
     * Updates all stop point tiles, removing hidden tiles and adding new tiles
     */
    this.updateTiles = function() {
        if (self.stopMap.map.getZoom() <= TILE_ZOOM) {
            return;
        }

        let tiles = self._getTileCoordinates();

        self.loadedStops.forEach(function(layer, coords) {
            let index = tiles.indexOf(coords);
            if (index > -1) {
                self.loadTile(coords);
                tiles.splice(index, 1);
            } else if (self.layers.hasLayer(layer)) {
                self.layers.removeLayer(layer);
            }
        });
        tiles.forEach(self.loadTile);
    };

    /**
     * Creates marker element to be used in map
     * @param {StopPoint} point Point object from data
     */
    this.markerElement = function(point) {
        let ind = '';
        if (point.properties.indicator !== '') {
            ind = '<span>' + point.properties.indicator + '</span>'
        } else if (point.properties.stopType === 'BCS' ||
                    point.properties.stopType === 'BCT') {
            ind = '<img src="' + BUS_SVG + '" width=28px alt="Bus stop">'
        } else if (point.properties.stopType === 'PLT') {
            ind = '<img src="' + TRAM_SVG + '" width=28px alt="Tram stop">'
        }

        let arrow = '';
        if (!self.isIE) {
            let bearing = 'indicator-marker__arrow--' + point.properties.bearing;
            arrow = '<div class="indicator-marker__arrow ' + bearing + '"></div>';
        }

        let area = 'area-' + point.properties.adminAreaRef;
        let indClass = 'indicator indicator-marker ' + area;

        return '<div class="' + indClass + '">' + arrow + ind + '</div>';
    };

    /**
     * Creates GeoJSON layer of stops from list of stops
     * @param {object} stops FeatureCollection data of stops within title
     */
    this.createLayer = function(stops) {
        return new L.GeoJSON(stops, {
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
                marker = marker.on('mouseover', function() {
                    self.zCount += 100;
                    this.setZIndexOffset(self.zCount);
                });
                // Add callback function to each marker with GeoJSON pointer object as argument
                marker = marker.on('click', function() {
                    self.stopMap.panel.setPanel(point);
                });

                return marker;
            }
        });
    };
}


/**
 * Handles tram/bus route on map
 * @constructor
 * @param {object} stopMap Parent stop map object
 */
function RouteLayer(stopMap) {
    let self = this;
    this.stopMap = stopMap;
    this.layer = null;

    /**
     * Creates route layer to be put on map
     * @param {object} route MultiLineString GeoJSON object
     */
    this.createLayer = function(route) {
        // TODO: Find colour for a specific style and use it for paths
        let className = 'area-' + route.properties.adminAreaCode;

        return new L.GeoJSON(route, {
            style: function() {
                return {className: className}
            }
        });
    };

    /**
     * Queries route for service ID and adds it to the map
     * @param {String} serviceId Service ID for route
     * @param {Boolean} direction Direction of service
     * @param {Boolean} zoom Whether map will zoom to fit route after load
     */
    this.addRoute = function(serviceId, direction, zoom) {
        let url = ROUTE_URL + serviceId;
        if (typeof(direction) !== 'undefined') {
            url += '?reverse=' + direction;
        }
        let request = new XMLHttpRequest;
        request.open('GET', url, true);

        request.addEventListener('load', function() {
            if (self.layer !== null) {
                self.removeRoute();
            }
            let data = JSON.parse(this.responseText);
            self.layer = self.createLayer(data.paths);
            self.layer.addTo(self.stopMap.map);
            // Rearrange layers with route behind markers and front of tiles
            self.layer.bringToBack();
            self.stopMap.tileLayer.bringToBack();
            if (typeof(zoom) !== 'undefined' || zoom) {
                self.stopMap.map.fitBounds(self.layer.getBounds());
            }
        });

        request.send();
    };

    /**
     * Removes route from map
     */
    this.removeRoute = function() {
        if (self.layer !== null) {
            self.stopMap.map.removeLayer(self.layer);
            self.layer = null;
        }
    };
}


/**
 * Handles the stop panel
 * @constructor
 * @param {object} stopMap Parent stop map object
 * @param {HTMLElement} mapPanel Panel HTML element
 * @param {boolean} cookieSet Whether the cookie has been set or not
 */
function StopPanel(stopMap, mapPanel, cookieSet) {
    let self = this;
    this.stopMap = stopMap;
    this.mapPanel = mapPanel;
    this.starred = new StarredStops(cookieSet, null);
    this.activeStops = new Map();

    /**
     * Gets live data object for a bus stop or create one if it does not exist
     * @param {string} atcoCode ATCO code for bus stop
     * @param {string} adminAreaRef Admin area code for bus stop
     * @param {string} table Table element ID
     * @param {string} time Heading element ID
     * @param {string} countdown Countdown element ID
     */
    this.getStop = function(atcoCode, adminAreaRef, table, time, countdown) {
        if (!self.activeStops.has(atcoCode)) {
            self.activeStops.set(atcoCode, new LiveData(
                atcoCode,
                adminAreaRef,
                table,
                time,
                countdown
            ));
        }

        self.stopAllLoops(atcoCode);
        self.activeStops.get(atcoCode).startLoop({
            end: function(atcoCode) {
                self.activeStops.delete(atcoCode);
            }
        });

        return self.activeStops.get(atcoCode);
    };

    /**
     * Finds the current stop shown on panel, or null if no stops are actively looping
     */
    this.getCurrentStop = function() {
        let currentData = null;
        self.activeStops.forEach(function(data) {
            if (data.loopActive && !data.loopEnding) {
                currentData = data;
            }
        });

        return currentData;
    };

    /**
     * Stops all loops
     * @param {string} exceptCode ATCO code for bus stop to be excluded
     */
    this.stopAllLoops = function(exceptCode) {
        self.activeStops.forEach(function(data, code) {
            if (typeof exceptCode === 'undefined' || code !== exceptCode) {
                data.stopLoop();
            }
        });
    };

    /**
     * Sets panel depending on existence of point data and zoom level
     * @param {?StopPoint} point If not null, displays stop point live data/info
     */
    self.setPanel = function(point) {
        if (point !== null) {
            self._setStopPanel(point);
        } else if (self.getCurrentStop() === null) {
            self._setPanelMessage();
        }
        self.stopMap.setURL();
    };

    /**
     * Clears all subelements from panel
     */
    this.clearPanel = function() {
        while (self.mapPanel.firstChild) {
            self.mapPanel.removeChild(self.mapPanel.firstChild);
        }
    };


    /**
     * Sets message on blank panel
     */
    this._setPanelMessage = function() {
        let heading = document.createElement('div');
        heading.className = 'heading heading--panel';

        let headingText = document.createElement('h2');
        if (self.stopMap.map.getZoom() <= TILE_ZOOM) {
            headingText.textContent = 'Zoom in to see stops';
        } else {
            headingText.textContent = 'Select a stop';
        }
        heading.appendChild(headingText);

        self.clearPanel();
        self.mapPanel.appendChild(heading);
    };


    /**
     * Sets panel for bus stop live data and other associated info
     * @param {StopPoint} point GeoJSON data for stop point
     */
    this._setStopPanel = function(point) {
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

        let actions = document.createElement('section');
        actions.className = 'card card--minor card--panel';
        let zoomTo = document.createElement('button');
        zoomTo.className = 'button';
        let zoomToInner = document.createElement('span');
        zoomToInner.textContent = 'Zoom to stop';
        zoomTo.appendChild(zoomToInner);
        zoomTo.onclick = function() {
            zoomTo.blur();
            self.stopMap.map.flyTo(
                L.latLng(point.geometry.coordinates[1], point.geometry.coordinates[0]), 18
            );
        };
        let visitStop = document.createElement('a');
        visitStop.className = 'button';
        visitStop.href = STOP_URL + point.properties.atcoCode;
        let visitStopInner = document.createElement('span');
        visitStopInner.textContent = 'View stop page';
        visitStop.appendChild(visitStopInner);
        actions.appendChild(zoomTo);
        actions.appendChild(visitStop);


        self.clearPanel();
        self.mapPanel.appendChild(headingOuter);
        resizeIndicator('indicator');
        self.mapPanel.appendChild(liveTimes);
        self.mapPanel.appendChild(stopInfo);
        self.mapPanel.appendChild(actions);

        self.getStop(
            point.properties.atcoCode,
            point.properties.adminAreaRef,
            'services',
            'live-time',
            'live-countdown'
        );

        self.starred.get(function() {
            let codeInList;
            if (!self.starred.set) {
                let info = document.createElement('div');
                info.className = 'hidden';
                info.style.margin = '-5px 0';
                let infoInner = document.createElement('p');
                infoInner.textContent = 'This will add a cookie to your device with a list of ' +
                    'starred stops. No other identifiable information is stored. If you\'re happy ' +
                    'with this, click again.';
                info.appendChild(infoInner);
                actions.appendChild(info);
                self.starred.info = info;
                codeInList = false;
            } else {
                codeInList = self.starred.data.indexOf(point.properties.naptanCode) > -1;
            }

            let starred = document.createElement('button');
            starred.className = 'button';
            let starredInner = document.createElement('span');
            starred.appendChild(starredInner);
            if (!self.starred.set || !codeInList) {
                starredInner.textContent = 'Add starred stop';
                starred.onclick = function() {
                    self.starred.add(starred, point.properties.naptanCode);
                };
            } else {
                starredInner.textContent = 'Remove starred stop';
                starred.onclick = function() {
                    self.starred.remove(starred, point.properties.naptanCode);
                };
            }
            actions.appendChild(starred);
        });
    };
}


/**
 * Handles the map container and stops
 * @constructor
 * @param {string} mapToken Mapbox token
 * @param {string} mapContainer ID for map container element
 * @param {string} mapPanel ID for map panel element
 * @param {boolean} cookieSet Whether the cookie has been set or not
 */
function StopMap(mapToken, mapContainer, mapPanel, cookieSet) {
    let self = this;
    this.mapContainer = document.getElementById(mapContainer);
    this.mapPanel = document.getElementById(mapPanel);

    this.map = null;
    this.tileLayer = L.tileLayer(
        'https://api.tiles.mapbox.com/v4/{id}/{z}/{x}/{y}.png?access_token={accessToken}',
        {
            minZoom: MAP_ZOOM_MIN,
            maxZoom: MAP_ZOOM_MAX,
            id: 'mapbox.emerald',
            accessToken: mapToken
        }
    );

    this.panel = new StopPanel(this, this.mapPanel, cookieSet);
    this.stops = new StopLayer(this);
    this.route = new RouteLayer(this);

    /**
     * Starts up the map and adds map events
     * @param {?StopPoint} point GeoJSON for initial stop point
     * @param {number} latitude Starts map at centre with latitude if point not defined
     * @param {number} longitude Starts map at centre with longitude if point not defined
     * @param {number} zoom Starts map at centre with zoom level if point not defined
     */
    this.init = function(point, latitude, longitude, zoom) {
        let coords,
            zoomLevel;
        if (latitude && longitude && zoom) {
            coords = L.latLng(latitude, longitude);
            zoomLevel = zoom;
        } else if (point !== null) {
            coords = L.latLng(point.geometry.coordinates[1], point.geometry.coordinates[0]);
            zoomLevel = MAP_ZOOM_MAX;
        } else {
            coords = L.latLng(MAP_CENTRE_GB);
            zoomLevel = MAP_ZOOM_MIN;
        }

        self.map = L.map(self.mapContainer.id, {
            zoom: zoomLevel,
            center: coords,
            minZoom: MAP_ZOOM_MIN,
            maxZoom: MAP_ZOOM_MAX,
            maxBounds: L.latLngBounds(
                L.latLng(MAP_BOUNDS_NW),
                L.latLng(MAP_BOUNDS_SE)
            ),
            attributionControl: false
        });

        self.map.on('zoomend', function() {
            if (self.map.getZoom() <= TILE_ZOOM) {
                self.stops.removeAllTiles();
            } else {
                self.stops.updateTiles();
            }
            self.panel.setPanel(null);
        });

        self.map.on('moveend', function() {
            self.setURL();
            self.stops.updateTiles();
        });

        self.map.on('click', function() {
            self.panel.stopAllLoops();
            self.panel.setPanel(null);
        });

        self.tileLayer.addTo(self.map);
        self.stops.init();
        self.stops.updateTiles();
        self.panel.setPanel(point);
    };

    /**
     * Sets page to new URL with current stop, coordinates and zoom
     */
    this.setURL = function() {
        let data = self.panel.getCurrentStop();
        let center = self.map.getCenter();
        let zoom = self.map.getZoom();
        let stop = (data !== null) ? 'stop/' + data.atcoCode + '/' : '';

        let newURL = MAP_URL + stop + center.lat + ',' + center.lng + ',' + zoom;
        history.replaceState(null, null, newURL);
    };
}


/**
 * Returns a SVG element with specified attributes
 * @param {string} tag SVG element tag
 * @param {object} [attr] Attributes for element
 * @returns {HTMLElement}
 * @private
 */
function _createSVGNode(tag, attr) {
    let node = document.createElementNS('http://www.w3.org/2000/svg', tag);

    if (typeof attr === 'undefined') {
        return node;
    }

    for (let a in attr) {
        if (attr.hasOwnProperty(a)) {
            node.setAttributeNS(null, a, attr[a]);
        }
    }

    return node;
}


/**
 * Creates a path command, eg 'C' and [[0, 0], [0, 1], [1, 1]] -> 'C 0,0 0,1 1,1'.
 * @param {string} command path command type, eg 'M' or 'L'
 * @param {Array} values Array of arrays, each containing numbers/coordinates
 * @returns {string}
 * @private
 */
function _pathCommand(command, ...values) {
    values.map(function(v) {
        return v.join(',');
    });

    return command + ' ' + values.join(' ');
}


/**
 * Get centre coordinates of element relative to a pair of coordinates.
 * @param {HTMLElement} element
 * @param {number} startX
 * @param {number} startY
 * @returns {{x: number, y: number}}
 * @private
 */
function _getRelativeElementCoords(element, startX, startY) {
    let rect = element.getBoundingClientRect();

    return {
        x: rect.left + rect.width / 2 - startX,
        y: rect.top + rect.height / 2 - startY
    };
}


/**
 * Finds the maximum value in a set.
 * @param {Set} set
 * @returns {*}
 * @private
 */
function _setMax(set) {
    let max = null;
    set.forEach(function(i) {
        if (max === null || i > max) {
            max = i;
        }
    });

    return max;
}


/**
 * Class for constructing service diagrams.
 * @constructor
 * @param {HTMLElement} container DOM node
 */
function Diagram(container) {
    let self = this;

    this.container = container;
    this.data = null;
    this.svg = null;
    this.rebuildTimeOut = null;

    this.listInd = null;
    this.colours = null;
    this.colStart = null;
    this.rowCoords = null;

    this.paths = [];
    this.definitions = [];
    this.col = new Set();
    this.row = new Set();

    /**
     * Sets stroke colour.
     * @param {{x1: number, y1: number, x2: number, y2: number}} c Coordinates for path.
     * @param {string} colour Main colour of path.
     * @param {object} [gradient] Gradient, either with a second colour or fade in/out.
     * @param {string} [gradient.colour] Second colour to be used.
     * @param {number} [gradient.fade] Whether this line fades in (1) or fades out (-1).
     * @returns {string} CSS value of colour or URL to gradient if required.
     * @private
     */
    this._setStroke = function(c, colour, gradient) {
        if (typeof gradient === 'undefined') {
            return colour;
        }
        let hasColour = gradient.hasOwnProperty('colour'),
            hasFade = gradient.hasOwnProperty('fade');

        if ((!hasFade || gradient.fade === 0) && !hasColour ||
            hasColour && colour === gradient.colour)
        {
            return colour;
        }
        if (hasFade && gradient.fade !== 0 && hasColour) {
            throw 'Fade and gradient colour cannot be used at the same time.';
        }

        let name = 'gradient-' + self.definitions.length,
            start, end, startColour, endColour;

        if (hasColour) {
            start = '35%';
            end = '65%';
            startColour = colour;
            endColour = gradient.colour;
        } else if (hasFade && gradient.fade < 0) {
            start = '40%';
            end = '100%';
            startColour = colour;
            endColour = LAYOUT_INVISIBLE;
        } else {
            start = '0%';
            end = '60%';
            startColour = LAYOUT_INVISIBLE;
            endColour = colour;
        }

        let gradientDef = _createSVGNode('linearGradient', {
            id: name,
            gradientUnits: 'userSpaceOnUse',
            x1: c.x1, x2: c.x2,
            y1: c.y1, y2: c.y2
        });
        gradientDef.appendChild(_createSVGNode('stop', {
            offset: start,
            'stop-color': startColour
        }));
        gradientDef.appendChild(_createSVGNode('stop', {
            offset: end,
            'stop-color': endColour
        }));
        self.definitions.push(gradientDef);

        return 'url(#' + name + ')';
    };

    /**
     * Adds path to diagram using coordinates.
     * @param {{x1: number, y1: number, x2: number, y2: number}} c Coordinates for path.
     * @param {string} colour Main colour of path.
     * @param {object} [gradient] Gradient, either with a second colour or fade in/out.
     * @param {string} [gradient.colour] Second colour to be used.
     * @param {number} [gradient.fade] Whether this line fades in (1) or fades out (-1).
     * No fading if zero or undefined.
     */
    this.addPathCoords = function(c, colour, gradient) {
        self.col.add(c.x1);
        self.col.add(c.x2);
        self.row.add(c.y1);
        self.row.add(c.y2);

        let path = _pathCommand('M', [c.x1, c.y1]),
            y = c.y2 - c.y1;
        if (c.x1 === c.x2) {
            path += ' ' + _pathCommand('L', [c.x2, c.y2]);
        } else {
            let i1 = c.y1 + y / LAYOUT_CURVE_MARGIN,
                i2 = c.y1 + y / 2,
                i3 = c.y1 + y - y / LAYOUT_CURVE_MARGIN;
            path += ' ' + _pathCommand('L', [c.x1, i1]);
            path += ' ' + _pathCommand('C', [c.x1, i2], [c.x2, i2], [c.x2, i3]);
            path += ' ' + _pathCommand('L', [c.x2, c.y2]);
        }

        let stroke = self._setStroke(c, colour, gradient);
        let pathNode = _createSVGNode('path', {
            'fill': 'none',
            'stroke': stroke,
            'stroke-width': LAYOUT_LINE_STROKE,
            'd': path
        });

        self.paths.push(pathNode);
    };

    /**
     * Adds path to diagram using row and column numbers.
     * @param {number} c1 Starting column number
     * @param {number} c2 Ending column number
     * @param {number} r Starting row number
     * @param {string} colour Main colour of path.
     * @param {object} [gradient] Gradient, either with a second colour or fade in/out.
     * @param {string} [gradient.colour] Second colour to be used.
     * @param {number} [gradient.fade] Whether this line fades in (1) or fades out (-1).
     * No fading if zero or undefined.
     */
    this.addPath = function(c1, c2, r, colour, gradient) {
        if (self.colStart === null || self.rowCoords === null) {
            throw 'Row and column coordinates need to be set first.';
        } else if (r < 0 || r >= self.rowCoords.length) {
            throw 'Row numbers need to be within range.';
        }

        let coords = {
            x1: self.colStart + c1 * LAYOUT_SPACE_X,
            y1: self.rowCoords[r],
            x2: self.colStart + c2 * LAYOUT_SPACE_X,
            y2: (r === data.length - 1) ?
                2 * self.rowCoords[r] - self.rowCoords[r - 1] : self.rowCoords[r + 1]
        };
        self.addPathCoords(coords, colour, gradient);
    };

    this.clear = function() {
        self.definitions = [];
        self.paths = [];
        self.col.clear();
        self.row.clear();

        if (self.container !== null && self.svg !== null) {
            self.container.removeChild(self.svg);
            self.svg = null;
        }
    };

    /**
     * Builds diagram and adds to container element.
     * @param {number} startX Starting x coordinate for line
     * @param {number} startY Starting y coordinate for line
     */
    this.build = function(startX, startY) {
        let boundsX = 2 * startX + (_setMax(self.col) + 2),
            boundsY = 2 * startY + _setMax(self.row);

        self.svg = _createSVGNode('svg', {width: boundsX, height: boundsY});

        if (self.definitions.length > 0) {
            let defs = _createSVGNode('defs');
            self.definitions.forEach(function(g) {
                defs.appendChild(g);
            });
            self.svg.appendChild(defs);
        }

        self.paths.forEach(function(p) {
            self.svg.appendChild(p);
        });

        self.container.appendChild(self.svg);
    };

    /**
     * Rebuilds diagram using data and updated coordinates of indicator elements.
     */
    this.rebuild = function() {
        let b = self.container.getBoundingClientRect(),
        coords = [],
        rows = [];

        self.listInd.forEach(function(stop) {
            let next = _getRelativeElementCoords(stop, b.left, b.top);
            coords.push(next);
            rows.push(next.y);
        });

        let startX = coords[0].x,
            startY = coords[0].y;

        if (self.svg === null) {
            self.colStart = startX;
            self.rowCoords = rows;
        } else if (self.rowCoords !== rows) {
            self.clear();
            self.rowCoords = rows;
        } else {
            // No need to change diagram
            return;
        }

        let previous = new Map(),
            current = new Map(),
            v0, v1, c0, c1;

        for (let r = 0; r < self.data.length; r++) {
            v0 = self.data[r];
            c0 = self.colours[r];
            v1 = null;
            c1 = null;
            if (r + 1 < self.data.length) {
                v1 = self.data[r + 1];
                c1 = self.colours[r + 1];
                if (c0 === null) {
                    c0 = c1;
                }
            }

            current = new Map();
            v0.paths.forEach(function(p) {
                let gradient = {},
                    start = (previous.has(p.start)) ? previous.get(p.start): c0;

                if (p.fade > 0) {
                    gradient['fade'] = p.fade;
                    current.set(p.end, start);
                } else if (p.fade < 0) {
                    gradient['fade'] = p.fade;
                } else if (v1 !== null && p.end === v1.column && start !== c1) {
                    gradient['colour'] = c1;
                    current.set(p.end, c1);
                } else {
                    current.set(p.end, start);
                }
                self.addPath(p.start, p.end, r, start, gradient);
            });
            previous = current;
        }

        self.build(startX, startY);
    };

    /**
     * Timer function to be used with window's event listener.
     */
    this.rebuildTimer = function() {
        if (self.rebuildTimeOut === null) {
            self.rebuildTimeOut = setTimeout(function() {
                self.rebuildTimeOut = null;
                self.rebuild();
            }, LAYOUT_TIMEOUT);
        }
    };

    /**
     * Sets up diagram and build
     * @param {Array} data
     */
    this.setUp = function(data) {
        self.data = data.map(function(v) {
            return {
                vertex: v[0],
                column: v[1],
                paths: v[2].map(function(p) {
                    return {start: p[0], end: p[1], fade: p[2]};
                })
            };
        });

        self.listInd = [];
        self.colours = [];
        self.data.forEach(function (v, i) {
            let code = (v.vertex !== null) ? v.vertex : 'Null';
            self.listInd.push(document.getElementById('i' + code));

            let colour;
            if (v.vertex !== null) {
                colour = getComputedStyle(self.listInd[i]).backgroundColor;
            } else {
                colour = null;
            }
            self.colours.push(colour);
        });

        self.rebuild();
        window.addEventListener('resize', self.rebuildTimer);
    };
}


function _moveStopItemElements(container, col, width) {
    let text = container.querySelector('.item__label'),
        p = container.querySelector('p');

    container.style.paddingLeft = LAYOUT_DOM_DIV_START + LAYOUT_SPACE_X * col + 'px';
    if (text !== null) {
        text.style.marginLeft = LAYOUT_DOM_TEXT_START +
            LAYOUT_SPACE_X * (width - col) + 'px';
    }
    if (p !== null) {
        p.style.paddingLeft = LAYOUT_DOM_PARA_START +
            LAYOUT_SPACE_X * (width - col) + 'px';
    }
}


function _addEmptyItem(list) {
    let item = document.createElement('li');
    let anchor = document.createElement('div');
    anchor.className = 'item item--stop item--stop--empty';
    anchor.id = 'cNull';

    let indicator = document.createElement('div');
    indicator.className = 'indicator';
    indicator.id = 'iNull';

    anchor.appendChild(indicator);
    item.appendChild(anchor);
    list.insertBefore(item, list.childNodes[0]);
}


/**
 * Draws diagram and add event listener to rebuild graph if required.
 * @param {(HTMLElement|string)} container DOM div node.
 * @param {(HTMLElement|string)} list DOM node for list of stops.
 * @param data Required data
 */
function setupGraph(container, list, data) {
    let containerElement = (container instanceof HTMLElement) ?
            container : document.getElementById(container),
        listStops = (list instanceof HTMLElement) ? list : document.getElementById(list);

    if (data[0][0] === null) {
        _addEmptyItem(listStops);
    }

    data.forEach(function(v, r) {
        let id = (v[0] !== null) ? v[0] : 'Null';
        let div = document.getElementById('c' + id);

        let cols = new Set();
        v[2].forEach(function(p) {
            cols.add(p[0]);
            cols.add(p[1]);
        });
        if (r > 0) {
            data[r - 1][2].forEach(function(p) {
                cols.add(p[1]);
            });
        }

        let width = (cols.size > 0) ? _setMax(cols) : 0;
        _moveStopItemElements(div, v[1], width);
    });

    let diagram = new Diagram(containerElement);
    diagram.setUp(data);

    return diagram;
}
