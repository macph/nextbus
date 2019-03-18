/*
 * nextbus website functionality, copyright Ewan Macpherson 2017-18
 */

const INTERVAL = 60;

const MAP_ZOOM_MIN = 7;
const MAP_ZOOM_MAX = 19;
const MAP_CENTRE_GB = [54.00366, -2.547855];
const MAP_BOUNDS_NW = [61, 2];
const MAP_BOUNDS_SE = [49, -8];

// Minimum number of degree places required to represent latitude and longitude at set zoom level
// Calculated using
// 1 degree longitude at equator = 111 320 m
// 1 pixel at zoom level 0 = 156 412 m
const MAP_DEG_ACCURACY = [0, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 4, 4, 4, 5, 5, 5, 5, 6, 6, 6, 7, 7, 7];

const CACHE_LIMIT = 64;
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
        console.debug('Browser does not support geolocation.');
        return;
    }

    let success = function(position) {
        let latitude = position.coords.latitude.toFixed(6);
        let longitude = position.coords.longitude.toFixed(6);
        console.debug('Current coordinates (' + latitude + ', ' + longitude + ')');
        // Direct to list of stops
        window.location.href = LocationURL + latitude + ',' + longitude;
    };

    let error = function(err) {
        console.debug('Geolocation error: ' + err);
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
            let newData = JSON.parse(self.r.responseText);
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
        if (transitions.hasOwnProperty(t) && typeof element.style[t] !== 'undefined') {
            return transitions[t];
        }
    }
}


/**
 * Adds events for showing search bar for most pages
 */
function addSearchBarEvents() {
    let barHidden = true;

    let searchButton = document.getElementById('header-search-button'),
        searchBar = document.getElementById('header-search-bar'),
        searchBarInput = document.getElementById('search-form'),
        searchBarTransitionEnd = getTransitionEnd(searchBar),
        searchSVG = document.getElementById('header-search-open'),
        closeSVG = document.getElementById('header-search-close');

    let transitionCallback = function() {
        searchBar.removeEventListener(searchBarTransitionEnd, transitionCallback);
        searchBarInput.focus();
    };

    let openSearchBar = function() {
        searchBar.classList.add('search-bar--open');
        searchSVG.style.display = 'none';
        closeSVG.style.display = '';
        searchButton.title = 'Close';
        searchButton.blur();
        barHidden = false;
        searchBar.addEventListener(searchBarTransitionEnd, transitionCallback);
    };

    let closeSearchBar = function() {
        searchBar.classList.remove('search-bar--open');
        searchSVG.style.display = '';
        closeSVG.style.display = 'none';
        searchButton.title = 'Search';
        searchBarInput.blur();
        barHidden = true;
    };

    searchButton.addEventListener('click', function() {
        (barHidden) ? openSearchBar() : closeSearchBar();
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
 * Resize text within indicators so they look better. Elements have a data attribute set so they can
 * be skipped the next time this function is called.
 * @param {...*} classes Class names as args to modify text in
 */
function resizeIndicator(...classes) {
    for (let i = 0; i < classes.length; i++) {
        let elements = document.getElementsByClassName(classes[i]);
        for (let j = 0; j < elements.length; j++) {
            let elt = elements[j];
            // Already covered previously; skip over
            if (elt.dataset.indicatorSet != null) {
                continue;
            }
            // Set data attribute and add class
            elt.dataset.indicatorSet = "1";
            let span = elt.querySelector('span');
            let img = elt.querySelector('img');
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
            } else if (img !== null) {
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
            // Already covered previously; skip over
            if (elt.dataset.coloursSet != null) {
                continue;
            }
            // Set data attribute and add class
            elt.dataset.coloursSet = "1";
            let style = window.getComputedStyle(elt);
            let foreground = style.getPropertyValue('color');
            let background = style.getPropertyValue('background-color');
            elt.style.backgroundColor = foreground;
            elt.style.color = background;
        }
    }
}

/**
 * Shorthand for creating a new element without namespace
 * @param {string} tag tag name
 * @param {?(object|HTMLElement|string|HTMLElement[]|string[])} attr object containing attributes
 * for new element, eg style, but can also be first child element or array of children if no
 * attributes are required
 * @param  {...?(HTMLElement|string|HTMLElement[]|string[])} children child elements or array of
 * elements to be appended
 * @returns {HTMLElement}
 */
function element(tag, attr, ...children) {
    let element = document.createElement(tag);

    if (attr == null && !children) {
        return element;
    }

    if (attr != null && (typeof attr === 'string' || attr instanceof HTMLElement ||
                         attr instanceof Array)) {
        children.unshift(attr);
    } else if (attr != null) {
        let a, s;
        for (a in attr) {
            if (!attr.hasOwnProperty(a)) {
                continue;
            }
            if (a === 'style') {
                for (s in attr['style']) {
                    if (attr['style'].hasOwnProperty(s)) {
                        element.style[s] = attr['style'][s];
                    }
                }
            } else {
                element[a] = attr[a];
            }
        }
    }

    let append = function(child) {
        if (child == null) {
            return;
        }
        if (typeof child == 'string') {
            element.appendChild(document.createTextNode(child));
        } else if (child instanceof HTMLElement) {
            element.appendChild(child);
        } else {
            throw new TypeError('Child element is not a valid HTML element or string.');
        }
    };

    if (children) {
        let i, c;
        for (i = 0; i < children.length; i++) {
            c = children[i];
            if (c instanceof Array) {
                c.forEach(append);
            } else {
                append(c);
            }
        }
    }

    return element;
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
    this.table = null;
    this.headingTime = null;
    this.headingCountdown = null;

    /**
     * Sets table, heading with time and subheading with countdown to specified elements
     * @param {(HTMLElement|string)} table
     * @param {(HTMLElement|string)} time
     * @param {(HTMLElement|string)} countdown
     */
    this.setElements = function(table, time, countdown) {
        self.table = (table instanceof HTMLElement) ? table : document.getElementById(table);
        self.headingTime = (time instanceof HTMLElement) ? time : document.getElementById(time);
        self.headingCountdown = (countdown instanceof HTMLElement) ?
            countdown : document.getElementById(countdown);
    };

    this.setElements(table, time, countdown);

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
                    console.debug('Request for stop ' + self.atcoCode + ' successful');
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

            let table = element('div', {className: 'list-services'});
            for (let s = 0; s < self.data.services.length; s++) {
                let service = self.data.services[s];
                let row = s + 1;

                // Cell showing bus line number
                let cNum = element('div',
                    {className: 'service service__line', style: {msGridRow: row}},
                    element('div',
                        {className: 'service service__line__inner area-' + self.adminAreaCode +
                                    ((service.name.length > 6) ? ' service__line--small' : '')},
                        element('span', service.name)
                    )
                );

                // Destination
                let cDest = element('div',
                    {className: 'service service__destination', style: {msGridRow: row}},
                    element('span', service.dest)
                );

                // Next bus due
                let cNext = element('div',
                    {className: 'service service__next', style: {msGridRow: row}},
                    element('span',
                        {className: (service.expected[0].live) ? clLive : ''},
                        self._strDue(service.expected[0].secs)
                    )
                );

                // Buses after
                let cAfter, cAfterSpan;
                // If number of expected services is 2, only need to show the 2nd service here
                if (service.expected.length === 2) {
                    cAfterSpan = element('span',
                        {className: (service.expected[1].live) ? clLive : ''},
                        self._strDue(service.expected[1].secs)
                    );
                // Otherwise, show the 2nd and 3rd services
                } else if (service.expected.length > 2) {
                    cAfterSpan = element('span',
                        element('span',
                            {className: (service.expected[1].live) ? clLive : ''},
                            self._strDue(service.expected[1].secs).replace(' min', '') + ' and'
                        ),
                        ' ',
                        element('span',
                            {className: (service.expected[2].live) ? clLive : ''},
                            self._strDue(service.expected[2].secs)
                        )
                    );
                }
                cAfter = element('div',
                    {className: 'service service__after', style: {msGridRow: row}},
                    cAfterSpan
                );

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
            console.debug('Created table with ' + self.data.services.length +
                          ' services for stop "' + self.atcoCode + '".');

        } else if (self.data !== null) {
            removeSubElements(self.table);
            if (self.isLive) {
                self.headingTime.textContent = 'No services expected at ' + self.data.localTime;
            } else {
                self.headingTime.textContent = 'No services found';
            }
            console.debug('No services found for stop ' + self.atcoCode + '.');
        } else {
            self.headingTime.textContent = 'Updating...';
            console.debug('No data received yet when printed for stop ' + self.atcoCode);
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
        console.debug('Live data overdue ' + overDue + ' minutes.');
    };

    /**
     * Called on start, every interval or when the loop ends.
     * @callback callbackLiveData
     * @param {string} atcoCode
     */

    /**
     * Starts up the loop with interval for refreshing. If the loop was ending it will continue as
     * normal.
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
 * Stores entries in map such that keys are stored in order and dropped if the max limit is
 * exceeded
 * @constructor
 * @param {number} max Max size of array before entries start being dropped
 */
function MapCache(max) {
    let self = this;
    this.max = max;
    this._data = new Map();

    Object.defineProperty(this, 'size', {
        get: function() {
            return this._data.size;
        }
    });

    /**
     * Gets value from map by key and push to front if requested
     * @param {*} key
     * @param {boolean} push Push key/value to front
     */
    this.get = function(key, push) {
        let obj = self._data.get(key);
        if (typeof obj === 'undefined') {
            return;
        }
        if (push) {
            self._data.delete(key);
            self._data.set(key, obj);
        }
        return obj;
    };

    /**
     * Adds key and entry, keeping to maximum size
     * @param {*} key
     * @param {*} entry
     */
    this.set = function(key, entry) {
        self._data.set(key, entry);
        if (self._data.size > self.max) {
            let first = null;
            self._data.forEach(function(entry, key) {
                if (first === null) {
                    first = key;
                }
            });
            self._data.delete(first);
        }
    };

    /**
     * Checks if coordinates exist in map
     * @param {*} key
     * @returns {boolean}
     */
    this.has = function(key) {
        return self._data.has(key);
    };

    /**
     * Iterates over each entry in map, with function accepting layer and coordinates objects
     * @param {function} func
     */
    this.forEach = function(func) {
        self._data.forEach(func);
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
 * Rounds floating point number to a set number of decimal places
 * @param {number} float
 * @param {number} places
 * @returns {number}
 */
function roundTo(float, places) {
    if (places < 0 || Math.round(places) !== places) {
        throw RangeError('Number of places must be a positive integer.');
    }
    let pow = Math.pow(10, places);
    return Math.round(float * pow) / pow;
}


/**
 * Creates control for map with buttons for each content, title and action
 * @param {{action: function, content: Element|string, title: ?string}} actions List of actions
 */
function mapControl(...actions) {
    let buttons = actions.map(function(a) {
        let titleText = (a.title != null) ? a.title : '';
        return element('a',
            {role: 'button', title: titleText, 'aria-label': titleText,
                  onclick: a.action, ondblclick: a.action},
            a.content
        );
    });

    let CustomControl = L.Control.extend({
        options: {position: 'topleft'},
        onAdd: function() {
            return element('div',
                {className: 'leaflet-bar leaflet-control leaflet-control-custom'},
                buttons
            );
        }
    });

    return new CustomControl();
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
 *         locality: string,
 *         adminAreaRef: string
 *     }
 * }} StopPoint
 */

/**
 * JSON data for each service associated with a stop point
 * @typedef {{
 *     id: number,
 *     description: string,
 *     line: string,
 *     direction: string,
 *     reverse: boolean,
 *     origin: string,
 *     destination: string,
 *     terminates: boolean
 * }} StopServiceData
 */

/**
 * Full JSON data for a stop point
 * @typedef {{
 *     atcoCode: string,
 *     naptanCode: string,
 *     title: string,
 *     name: string,
 *     indicator: string,
 *     street: ?string,
 *     crossing: ?string,
 *     landmark: ?string,
 *     bearing: ?string,
 *     stopType: string,
 *     adminAreaRef: string,
 *     latitude: number,
 *     longitude: number,
 *     adminArea: {code: string, name: string},
 *     district: ?{code: string, name: string},
 *     locality: {code: string, name: string},
 *     services: StopServiceData[]
 * }} StopPointData
 */

/**
 * GeoJSON object for creating route layer
 * @typedef {{
 *     type: string,
 *     geometry: {
 *         type: string,
 *         coordinates: number[][]
 *     }
 * }} RoutePaths
 */

/**
 * Data for service route
 * @typedef {{
 *     service: string,
 *     line: string,
 *     description: string,
 *     direction: string,
 *     reverse: boolean,
 *     mirrored: boolean,
 *     operators: string[],
 *     stops: StopPoint[],
 *     sequence: string[],
 *     paths: RoutePaths,
 *     layout: Array
 * }} ServiceData
 */


/**
 * Creates indicator element from stop point data
 * @param {{indicator: string, stopType: string}} stopData
 * @returns {?HTMLElement}
 */
function createIndicator(stopData) {
    let ind;
    if (stopData.indicator !== '') {
        ind = element('span', stopData.indicator);
    } else if (stopData.stopType === 'BCS' || stopData.stopType === 'BCT') {
        ind = element('img', {src: STATIC + 'img/bus-white.svg', width: '28', alt: 'Bus stop'});
    } else if (stopData.stopType === 'PLT') {
        ind = element('img', {src: STATIC + 'img/tram-white.svg', width: '28', alt: 'Tram stop'});
    } else {
        ind = null;
    }

    return ind;
}


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
    this.loadedTiles = new MapCache(CACHE_LIMIT);
    this.layers = L.layerGroup();
    this.route = null;
    this.data = null;

    /**
     * Create hash with Cantor pairing function
     * @param {{x: number, y: number}} coords
     */
    this.hash = function(coords) {
        return 0.5 * (coords.x + coords.y) * (coords.x + coords.y + 1) + coords.y;
    };

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
        let key = self.hash(coords);
        let obj = self.loadedTiles.get(key, true);
        if (typeof obj !== 'undefined') {
            if (obj !== null) {
                self.layers.addLayer(obj.layer);
                resizeIndicator('indicator-marker');
            }
            return;
        }

        let url = TILE_URL + coords.x + ',' + coords.y;
        let request = new XMLHttpRequest;
        request.open('GET', url, true);

        request.onload = function() {
            let data = JSON.parse(request.responseText);
            if (data.features.length > 0) {
                let layer = self.createLayer(data);
                self.loadedTiles.set(key, {coords: coords, layer: layer});
                self.layers.addLayer(layer);
                resizeIndicator('indicator-marker');
            } else {
                self.loadedTiles.set(key, null);
            }
        };

        request.send();
    };

    /**
     * Removes all tiles and route stops - but data stays in cache
     */
    this.removeAllTiles = function() {
        self.layers.eachLayer(function(layer) {
            self.layers.removeLayer(layer);
        });
    };

    /**
     * Converts latitude longitude coordinates to grid coordinates at TILE_ZOOM
     * @param {L.Point} scale
     * @param {L.LatLng} coords
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
     * Updates all stop point tiles or route stops, removing hidden tiles and adding new tiles
     */
    this.updateTiles = function() {
        if (self.stopMap.map.getZoom() <= TILE_ZOOM) {
            return;
        }
        if (self.route === null) {
            let tiles = self._getTileCoordinates();
            self.loadedTiles.forEach(function(entry) {
                if (entry !== null) {
                    let index = tiles.indexOf(entry.coords);
                    if (index > -1) {
                        self.loadTile(entry.coords);
                        tiles.splice(index, 1);
                    } else if (self.layers.hasLayer(entry.layer)) {
                        self.layers.removeLayer(entry.layer);
                    }
                }
            });
            tiles.forEach(self.loadTile);
        } else if (!self.layers.hasLayer(self.route)) {
            self.route.addTo(self.layers);
            resizeIndicator('indicator-marker');
        }
    };

    /**
     * Creates marker element to be used in map
     * @param {StopPoint} stop Point object from data
     * @returns {HTMLElement} Element for marker
     * @private
     */
    this._markerElement = function(stop) {
        let arrow = null;
        if (!self.isIE) {
            let className = 'indicator-marker__arrow';
            if (stop.properties.bearing) {
                className += ' ' + 'indicator-marker__arrow--' + stop.properties.bearing;
            }
            arrow = element('div', {className: className})
        }

        return element('div',
            {className: 'indicator indicator-marker area-' + stop.properties.adminAreaRef},
            arrow,
            createIndicator(stop.properties)
        );
    };

    /**
     * Creates GeoJSON layer of stops from list of stops
     * @param {{
     *     type: string,
     *     features: StopPoint[]
     * }} stops FeatureCollection data of stops within title
     */
    this.createLayer = function(stops) {
        return L.geoJSON(stops, {
            pointToLayer: function(stop, latLng) {
                let icon = L.divIcon({
                    className: 'marker',
                    iconSize: null,
                    html: self._markerElement(stop).outerHTML
                });
                let marker = L.marker(latLng, {
                        icon: icon,
                        title: stop.properties.title,
                        alt: stop.properties.indicator
                });
                // Move marker to front when mousing over
                marker = marker.on('mouseover', function() {
                    self.zCount += 100;
                    this.setZIndexOffset(self.zCount);
                });
                // Add callback function to each marker with GeoJSON point object as argument
                marker = marker.on('click', function() {
                    self.stopMap.update({stop: stop.properties.atcoCode});
                });

                return marker;
            }
        });
    };

    /**
     * Creates layer of stops on route and sets layer such that only these route stops are loaded
     * @param {ServiceData} data
     */
    this.setRoute = function(data) {
        let stops = [];
        for (let s in data.stops) {
            if (data.stops.hasOwnProperty(s)) {
                stops.push(data.stops[s]);
            }
        }
        self.route = self.createLayer({type: 'FeatureCollection', features: stops});
        self.removeAllTiles();
        self.updateTiles();
    };

    /**
     * Removes route from layer, and tiles will be loaded as usual
     */
    this.removeRoute = function() {
        self.route = null;
        self.removeAllTiles();
        self.updateTiles();
    };

    /**
     * Sets current stop
     */
    this.setStop = function(data) {
        self.data = data;
    };

    /**
     * Clears current stop
     */
    this.removeStop = function() {
        self.data = null;
    };
}


/**
 * Holds stop point data for panels.
 * @constructor
 */
function StopPointsData() {
    let self = this;
    this.loadedStops = new MapCache(CACHE_LIMIT);

    /**
     * Gets data for stop point without doing a call.
     * @param {string} atcoCode
     * @returns {StopPointData}
     */
    this.get = function(atcoCode) {
        return self.loadedStops.get(atcoCode);
    };

    /**
     * @callback onLoadData
     * @param {StopPointData} data
     */

    /**
     * @callback failLoadData
     * @param {XMLHttpRequest} request
     */

    /**
     * Collects stop data, using callback on successful retrieval
     * @param {string} atcoCode
     * @param {onLoadData} [onLoad] Callback on successful request
     * @param {failLoadData} [onError] Callback on request error
     */
    this.retrieve = function(atcoCode, onLoad, onError) {
        if (self.loadedStops.has(atcoCode)) {
            let data = self.loadedStops.get(atcoCode);
            if (onLoad) {
                onLoad(data);
            }
            return;
        }

        let request = new XMLHttpRequest;
        request.open('GET', STOP_URL + atcoCode, true);
        request.onreadystatechange = function() {
            if (request.readyState === XMLHttpRequest.DONE && request.status === 200) {
                let data = JSON.parse(request.responseText);
                self.loadedStops.set(atcoCode, data);
                if (onLoad) {
                    onLoad(data);
                }
            } else if (request.readyState === XMLHttpRequest.DONE && onError) {
                onError(request);
            }
        };

        request.send();
    };
}


/**
 * @typedef {{id: string, reverse: ?boolean}} ServiceID
 */


/**
 * Gets URL component used to identify data for routes.
 * @param {ServiceID} service
 * @returns {string}
 */
function urlPart(service) {
    let url = service.id;
    if (service.reverse != null) {
        url += '/';
        url += (service.reverse) ? 'inbound' : 'outbound';
    }
    return url;
}


/**
 * Handles route data.
 * @constructor
 */
function ServicesData() {
    let self = this;
    this.loadedRoutes = new MapCache(CACHE_LIMIT);

    /**
     * Gets data for service ID and direction without doing a call.
     * @param {ServiceID} service Service ID and direction for route
     * @returns {ServiceData} Service data
     */
    this.get = function(service) {
        return self.loadedRoutes.get(urlPart(service));
    };

    /**
     * @callback onLoadData
     * @param {ServiceData} data
     */

    /**
     * @callback failLoadData
     * @param {XMLHttpRequest} request
     */

    /**
     * Collects route data, using callback on successful retrieval
     * @param {ServiceID} service Service ID and direction for route
     * @param {onLoadData} [onLoad] Callback on successful request
     * @param {failLoadData} [onError] Callback on request error
     */
    this.retrieve = function(service, onLoad, onError) {
        let part = urlPart(service);

        if (self.loadedRoutes.has(part)) {
            let data = self.loadedRoutes.get(part);
            if (onLoad) {
                onLoad(data);
            }
            return;
        }

        let request = new XMLHttpRequest;
        request.open('GET', ROUTE_URL + part, true);
        request.onreadystatechange = function() {
            if (request.readyState === XMLHttpRequest.DONE && request.status === 200) {
                let data = JSON.parse(request.responseText);
                self.loadedRoutes.set(part, data);
                if (onLoad) {
                    onLoad(data);
                }
            } else if (request.readyState === XMLHttpRequest.DONE && onError) {
                onError(request);
            }
        };

        request.send();
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

    this.current = null;
    this.data = null;
    this.layer = null;

    /**
     * Creates route layer to be put on map
     * @param {ServiceData} data Service data with MultiLineString GeoJSON object
     */
    this.createLayer = function(data) {
        // TODO: Find colour for a specific style and use it for paths
        let paths = L.geoJSON(data.paths, {
            style: function() {
                return {color: 'rgb(0, 33, 113)'}
            }
        });
        paths.on('click', function() {
            self.stopMap.update({stop: null});
        });

        return paths;
    };

    /**
     * Removes layer from map and sets data to null
     */
    this.clearLayer = function() {
        if (self.layer !== null) {
            self.stopMap.map.removeLayer(self.layer);
        }
        self.data = null;
        self.layer = null;
    };

    /**
     * Loads new route layer.
     * @param {ServiceData} data Route data to load
     * @param {boolean} [fit] Fits map to service paths
     */
    this.loadLayer = function(data, fit) {
        if (self.data !== data) {
            self.clearLayer();
            self.data = data;
            self.layer = self.createLayer(data);

            self.layer.addTo(self.stopMap.map);
            // Rearrange layers with route behind markers and front of tiles
            self.layer.bringToBack();
            self.stopMap.tileLayer.bringToBack();
        }
        if (fit) {
            self.stopMap.map.fitBounds(self.layer.getBounds());
        }
    };

    /**
     * Sets paths on map using service data.
     * @param {ServiceID} service Service ID and direction for route
     * @param {boolean} [fit] Fits map to service paths
     */
    this.set = function(service, fit) {
        self.current = service;
        self.stopMap.services.retrieve(service, function(data) {
            // Route only loads if it's the one most recently called
            if (self.current === service) {
                self.loadLayer(data, fit);
            }
        });
    };

    /**
     * Clears the route and associated data from map
     */
    this.clear = function() {
        self.current = null;
        self.clearLayer();
    };
}


/**
 * Handles the panel
 * @constructor
 * @param {object} stopMap Parent stop map object
 * @param {HTMLElement} mapPanel Panel HTML element
 * @param {boolean} cookieSet Whether the cookie has been set or not
 */
function Panel(stopMap, mapPanel, cookieSet) {
    let self = this;
    this.stopMap = stopMap;
    this.mapPanel = mapPanel;
    this.container = this.mapPanel.parentNode;
    this.starred = new StarredStops(cookieSet, null);
    this.activeStops = new Map();
    this.currentMapControl = null;

    this.currentStop = null;
    this.currentService = null;

    this.directions = {
        'N': 'northbound',
        'NE': 'northeast bound',
        'E': 'eastbound',
        'SE': 'southeast bound',
        'S': 'southbound',
        'SW': 'southwest bound',
        'W': 'westbound',
        'NW': 'northwest bound'
    };

    /**
     * Gets live data object for a bus stop or create one if it does not exist
     * @param {string} atcoCode ATCO code for bus stop
     * @param {string} adminAreaRef Admin area code for bus stop
     * @param {(HTMLElement|string)} table Table element ID
     * @param {(HTMLElement|string)} time Heading element ID
     * @param {(HTMLElement|string)} countdown Countdown element ID
     */
    this.getStop = function(atcoCode, adminAreaRef, table, time, countdown) {
        let live;
        if (!self.activeStops.has(atcoCode)) {
            live = new LiveData(
                atcoCode,
                adminAreaRef,
                table,
                time,
                countdown
            );
            self.activeStops.set(atcoCode, live);
        } else {
            live = self.activeStops.get(atcoCode);
            live.setElements(table, time, countdown);
        }

        self.stopAllLoops(atcoCode);
        live.startLoop({
            end: function(atcoCode) {
                self.activeStops.delete(atcoCode);
            }
        });

        return live;
    };

    /**
     * Stops all loops
     * @param {string} [exceptCode] ATCO code for bus stop to be excluded
     */
    this.stopAllLoops = function(exceptCode) {
        self.activeStops.forEach(function(data, code) {
            if (typeof exceptCode === 'undefined' || code !== exceptCode) {
                data.stopLoop();
            }
        });
    };

    /**
     * Sets panel to a stop point with live times or a service diagram based on stops and services
     * being loaded by map
     */
    this.updatePanel = function() {
        let updateStop = (self.stopMap.currentStop !== self.currentStop),
            updateService = (self.stopMap.currentService !== self.currentService);

        if (self.stopMap.currentStop && (updateStop || updateService)) {
            // Set to a new stop or keep current stop and set new service
            self.currentService = self.stopMap.currentService;
            self.currentStop = self.stopMap.currentStop;
            self._scrollToTop();
            self._setStopPanel();
        } else if (!self.stopMap.currentStop && self.stopMap.currentService &&
                   (updateStop || updateService)) {
            // Unset any current stops and return to original service, or set new service
            self.currentStop = null;
            self.currentService = self.stopMap.currentService;
            self.stopAllLoops();
            self._scrollToTop();
            self._setServicePanel();
        } else if (!self.stopMap.currentStop && !self.stopMap.currentService) {
            // Unset any current stops and services
            self.currentStop = null;
            self.currentService = null;
            self.stopAllLoops();
            self._scrollToTop();
            self._setPanelMessage();
        }
    };

    /**
     * Clears all subelements and map control from panel
     */
    this.clearPanel = function() {
        removeSubElements(self.mapPanel);
        if (self.currentMapControl != null) {
            self.stopMap.map.removeControl(self.currentMapControl);
            self.currentMapControl = null;
        }
    };

    /**
     * Reset scroll positions within both landscape or portrait/mobile layouts
     * @private
     */
    this._scrollToTop = function() {
        // Scroll within container to top
        self.container.scrollTop = 0;
        // Scroll to just above container if top of container not in view
        let rect = self.container.getBoundingClientRect(),
            docEl = document.documentElement,
            offset = window.pageYOffset || docEl.scrollTop || document.body.scrollTop;
        if (rect.top < 0) {
            window.scrollTo(0, offset + rect.top - 48);
        }
    };

    /**
     * Sets message on blank panel
     * @param {string} [text] Optional text to display
     * @private
     */
    this._setPanelMessage = function(text) {
        let headingText;
        if (text) {
            headingText = text;
        } else if (self.stopMap.map.getZoom() <= TILE_ZOOM) {
            headingText = 'Zoom in to see stops';
        } else {
            headingText = 'Select a stop';
        }

        let heading = element('div',
            {className: 'heading heading--panel'},
            element('h2', headingText)
        );

        self.clearPanel();
        self.mapPanel.appendChild(heading);
    };


    /**
     * Sets panel for bus stop live data and other associated info
     * @param {StopPointData} data Data for stop point, locality and services
     * @private
     */
    this._setStopPanelData = function(data) {
        let headingText = null,
            hasBearing = (data.bearing !== null && self.directions.hasOwnProperty(data.bearing)),
            hasStreet = (data.street !== null);

        if (hasBearing && hasStreet) {
            headingText = element('p',
                element('strong', data.street),
                ', ',
                self.directions[data.bearing]
            );
        } else if (hasBearing) {
            let dirText = self.directions[data.bearing];
            headingText = element('p', dirText.charAt(0).toUpperCase() + dirText.slice(1));
        } else if (hasStreet) {
            headingText = element('p', element('strong', data.street));
        }

        let leaveTitle, leaveSrc, leaveAlt;
        if (self.currentService !== null) {
            let data = self.stopMap.routeLayer.data;
            leaveTitle = 'Back to service ' + data.line;
            leaveSrc = 'icons/sharp-timeline-24px.svg';
            leaveAlt = 'Back';
        } else {
            leaveTitle = 'Close stop panel';
            leaveSrc = 'icons/sharp-close-24px.svg';
            leaveAlt = 'Close';
        }

        let headingOuter = element('div',
            {className: 'heading heading--panel'},
            element('button',
                {
                    className: 'button button--action button--action--float',
                    title: leaveTitle,
                    onclick: function() {
                        this.blur();
                        self.stopMap.update({stop: null});
                        return false;
                    }
                },
                element('img', {src: STATIC + leaveSrc, alt: leaveAlt})
            ),
            element('div',
                {className: 'heading-stop'},
                element('div',
                    {className: 'indicator area-' + data.adminAreaRef},
                    createIndicator(data)
                ),
                element('h1', data.name)
            ),
            headingText
        );

        let liveTimes = element('section',
            {className: 'card card--panel'},
            element('div',
                {className: 'heading-inline heading-inline--right'},
                element('h2', {id: 'live-time'}, 'Retrieving live data...'),
                element('p', {id: 'live-countdown'})
            ),
            element('div', {id: 'services'})
        );

        let services = element('section',
            {className: 'card card--panel'},
            element('h2', 'Services')
        );

        if (data.services) {
            let listNonTerminating = [],
                listTerminating = [];
            data.services.forEach(function(s) {
                let listItem = element('li',
                    element('div',
                        {className: 'item item--service', onclick: function() {
                            self.stopMap.update({
                                stop: null,
                                service: {id: s.id, reverse: s.reverse},
                                fitService: true
                            });
                        }},
                        element('div',
                            {className: 'line'},
                            element('div',
                                {className: 'line__inner area-' + data.adminAreaRef},
                                element('span', {className: 'line__text'}, s.line)
                            )
                        ),
                        element('div',
                            {className: 'item__label'},
                            (s.terminates) ? 'from ' + s.origin : s.destination
                        )
                    )
                );
                if (s.terminates) {
                    listTerminating.push(listItem);
                } else {
                    listNonTerminating.push(listItem);
                }
            });

            services.appendChild(element('ul', {className: 'list'}, listNonTerminating));

            // Add terminating services under own section
            if (listTerminating.length > 0) {
                services.appendChild(element('h3', 'Terminating services'));
                services.appendChild(element('ul', {className: 'list'}, listTerminating));
            }
        } else {
            services.appendChild(element('p', 'No services stop here.'));
        }

        let infoLine = null,
            infoSet = [];
        if (data.street) {
            infoSet.push(element('strong', data.street));
        }
        if (data.crossing) {
            infoSet.push(data.crossing);
        }
        if (data.landmark) {
            infoSet.push(data.landmark);
        }
        if (infoSet) {
            let i;
            for (i = infoSet.length - 1; i > 0; i--) {
                infoSet.splice(i, 0, ', ');
            }
            infoLine = element('p', infoSet);
        }

        let stopInfo = element('section',
            {className: 'card card--panel'},
            element('h2', 'Stop Information'),
            infoLine,
            element('p', 'SMS code ', element('strong', data.naptanCode))
        );

        let actions = element('section',
            {className: 'card card--minor card--panel'},
            element('a',
                {className: 'button', href: STOP_PAGE_URL + data.atcoCode},
                'Stop page'
            )
        );
        self.clearPanel();
        self.mapPanel.appendChild(headingOuter);
        resizeIndicator('indicator');
        self.mapPanel.appendChild(liveTimes);
        self.mapPanel.appendChild(services);
        self.mapPanel.appendChild(stopInfo);
        self.mapPanel.appendChild(actions);

        self.getStop(
            data.atcoCode,
            data.adminAreaRef,
            'services',
            'live-time',
            'live-countdown'
        );

        self.starred.get(function() {
            let codeInList;
            if (!self.starred.set) {
                let info = element('div',
                    {className: 'hidden', style: {margin: '-5px 10px'}},
                    element('p',
                        'This will add a cookie to your device with a list of starred stops. No ' +
                        'other identifiable information is stored. If you\'re happy with this, ' +
                        'click again.'
                    )
                );
                actions.appendChild(info);
                self.starred.info = info;
                codeInList = false;
            } else {
                codeInList = self.starred.data.indexOf(data.naptanCode) > -1;
            }

            let starredAction, starredText;
            if (!self.starred.set || !codeInList) {
                starredAction = function() {
                    self.starred.add(starred, data.naptanCode);
                };
                starredText = 'Add starred stop';
            } else {
                starredAction = function() {
                    self.starred.remove(starred, data.naptanCode);
                };
                starredText = 'Remove starred stop';
            }
            let starred = element('button',
                {className: 'button', onclick: starredAction},
                starredText
            );
            actions.appendChild(starred);
        });

        // Add control for zooming into stop view
        self.currentMapControl = mapControl({
            action: function() {
                self.stopMap.map.flyTo(L.latLng(data.latitude, data.longitude), 18);
            },
            content: element('img', {src: STATIC + 'icons/sharp-zoom_out_map-24px.svg', alt: 'F'}),
            title: 'Fly to stop'
        });
        self.currentMapControl.addTo(self.stopMap.map);
    };

    /**
     * Sets panel for bus stop live data and other associated info
     * @private
     */
    this._setStopPanel = function() {
        self.stopMap.stops.retrieve(self.currentStop, self._setStopPanelData);
    };

    /**
     * Draws service panel
     * @param {ServiceData} data
     * @private
     */
    this._setServicePanelData = function(data) {
        let listOperators = null;
        if (data.operators) {
            listOperators = [];
            data.operators.forEach(function(op, i) {
                listOperators.push(element('strong', op));
                if (i < data.operators.length - 2) {
                    listOperators.push(', ');
                } else if (i === data.operators.length - 2) {
                    listOperators.push(' and ');
                }
            });
        }

        let direction = (data.reverse) ? 'inbound' : 'outbound',
            timetableURL = TIMETABLE_URL.replace('//', '/' + data.service + '/' + direction + '/');

        let headingOuter = element('div',
            {className: 'heading heading--panel'},
            element('button',
                {
                    className: 'button button--action button--action--float',
                    title: 'Close service panel',
                    onclick: function() {
                        this.blur();
                        self.stopMap.update({service: null});
                    }
                },
                element('img', {src: STATIC + 'icons/sharp-close-24px.svg', alt: 'Close'})
            ),
            element('div',
                {className: 'heading-service'},
                element('div',
                    {className: 'line'},
                    element('div',
                        {className: 'line__inner'},
                        element('span', {className: 'line__text'}, data.line)
                    )
                ),
                element('h1', data.description)
            ),
            element('div',
                {className: 'heading-subtitle'},
                element('p',
                    {className: 'heading-subtitle__operator'},
                    'Operated by ',
                    listOperators
                ),
                element('div',
                    {className: 'heading-subtitle__buttons'},
                    element('a',
                        {className: 'button', href: timetableURL},
                        'Timetable'
                    )
                )
            )
        );

        let tabs = null;
        if (data.mirrored) {
            tabs = element('ul',
                {className: 'tabs tabs--panel tabs--2'},
                element('li',
                    element('div',
                        {className: (data.reverse) ? 'tab' : 'tab tab--active',
                         onclick: (data.reverse) ? function() {
                             map.update({service: {id: data.service, reverse: false}});
                         } : null},
                        'Outbound'
                    )
                ),
                element('li',
                    element('div',
                        {className: (data.reverse) ? 'tab tab--active' : 'tab',
                         onclick: (data.reverse) ? null : function() {
                             map.update({service: {id: data.service, reverse: true}});
                         }},
                        'Inbound'
                    )
                )
            );
        }

        let list = element('section', {className: 'card card--panel card--relative'}),
            diagram = element('div', {className: 'diagram'});

        let listStops = null;
        if (data.sequence) {
            listStops = element('ul', {className: 'list list--relative'});
            data.sequence.forEach(function(code) {
                let s = data.stops[code],
                    item;
                if (code) {
                    item = element('div',
                        {className: 'item item--stop--multiline item--stop--service'}
                    );

                    let sub = [];
                    if (s.properties.street) {
                        sub.push(s.properties.street);
                    }
                    if (s.properties.locality) {
                        sub.push(s.properties.locality)
                    }
                    let subtitle = (sub) ? element('p', sub.join(', ')) : null;

                    let inner = element('div',
                        {id: 'c' + s.properties.atcoCode},
                        element('div',
                            {className: 'item--stop'},
                            element('div',
                                {className: 'indicator area-' + s.properties.adminAreaRef,
                                 id: 'i' + s.properties.atcoCode},
                                createIndicator(s.properties)
                            ),
                            element('div', {className: 'item__label'}, s.properties.name),
                        ),
                        subtitle
                    );

                    item.appendChild(inner);
                    item.onmouseover = function() {
                        let coords = L.latLng(s.geometry.coordinates[1], s.geometry.coordinates[0]);
                        if (!self.stopMap.map.getBounds().contains(coords)) {
                            self.stopMap.map.panTo(coords);
                        }
                    };
                    item.onclick = function() {
                        self.stopMap.update({stop: s.properties.atcoCode, fitStop: true});
                    };
                } else {
                    item = element('div',
                        {className: 'item item--stop item--stop--empty', id: 'cNull'},
                        element('div', {className: 'indicator', id: 'iNull'})
                    );
                }
                listStops.appendChild(element('li', item));
            });
        } else {
            listStops = element('p', 'No stops for this service.');
        }

        list.appendChild(diagram);
        list.appendChild(listStops);

        self.clearPanel();
        self.mapPanel.appendChild(headingOuter);
        if (tabs) {
            self.mapPanel.appendChild(tabs);
        }
        self.mapPanel.appendChild(list);

        // Add control for fitting service to map
        self.currentMapControl = mapControl({
            action: function() {
                self.stopMap.map.fitBounds(self.stopMap.routeLayer.layer.getBounds());
            },
            content: element('img', {src: STATIC + 'icons/sharp-zoom_out_map-24px.svg', alt: 'F'}),
            title: 'Fit route to map'
        });
        self.currentMapControl.addTo(self.stopMap.map);

        if (data.stops) {
            resizeIndicator('indicator');
            setupGraph(diagram, data.layout);
        }
    };

    /**
     * Draws service panel after getting data
     * @private
     */
    this._setServicePanel = function() {
        self.stopMap.services.retrieve(self.currentService, self._setServicePanelData);
    };
}


// TODO: SVG diagram extends past bottom of list into footer. Can an extra row be added?


/**
 * Handles the map container and stops
 * @constructor
 * @param {string} mapContainer ID for map container element
 * @param {string} mapPanel ID for map panel element
 * @param {boolean} cookieSet Whether the cookie has been set or not
 * @param {boolean} useGeolocation Enable geolocation on this map
 */
function StopMap(mapContainer, mapPanel, cookieSet, useGeolocation) {
    let self = this;
    this.mapContainer = document.getElementById(mapContainer);
    this.mapPanel = document.getElementById(mapPanel);
    this.geolocation = useGeolocation;

    this.map = null;
    this.tileLayer = L.tileLayer(
        'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
        {
            minZoom: MAP_ZOOM_MIN,
            maxZoom: MAP_ZOOM_MAX,
            subdomains: 'abcd',
            attribution:
                '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> ' +
                'contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
        }
    );

    this.panel = new Panel(this, this.mapPanel, cookieSet);
    this.services = new ServicesData();
    this.stops = new StopPointsData();
    this.stopLayer = new StopLayer(this);
    this.routeLayer = new RouteLayer(this);

    this.currentStop = null;
    this.currentService = null;

    this._addMapControls = function() {
        let ZoomControl = L.Control.Zoom.extend({
            options: {
                position: 'topleft'
            },
            onAdd: function (map) {
                let containerClass = 'leaflet-control-zoom leaflet-bar leaflet-control-custom',
                    icons = STATIC + 'icons/',
                    container = element('div', {className: containerClass}),
                    zoomIn = element('img', {src: icons + 'sharp-add-24px.svg', alt: '+'}),
                    zoomOut = element('img', {src: icons + 'sharp-remove-24px.svg', alt: '-'});

                this._zoomInButton  = this._createButton(zoomIn.outerHTML, this.options.zoomInTitle,
                    'leaflet-control-zoom-in', container, this._zoomIn);
                this._zoomOutButton = this._createButton(zoomOut.outerHTML, this.options.zoomOutTitle,
                    'leaflet-control-zoom-out', container, this._zoomOut);

                this._updateDisabled();
                map.on('zoomend zoomlevelschange', this._updateDisabled, this);

                return container;
            },
        });

        new ZoomControl().addTo(self.map);

        if (self.geolocation) {
            self.map.on('locationfound', function (e) {
                self.map.setView([e.latitude, e.longitude], TILE_ZOOM + 1);
                self.update({stop: null, service: null});
            });
            mapControl({
                action: function() {
                    self.map.locate();
                },
                content: element('img', {src: STATIC + 'icons/sharp-my_location-24px.svg', alt: 'G'}),
                title: 'Set map to your location'
            }).addTo(self.map);
        }
    };

    this._initComponents = function(stop, service, fitStop, fitService) {
        self.tileLayer.addTo(self.map);
        self.stopLayer.init();

        // Set map view to centre of GB at min zoom if not set yet
        if (self.map.getZoom() == null) {
            self.map.setView(L.latLng(MAP_CENTRE_GB), MAP_ZOOM_MIN);
        }

        self.update({
            stop: stop,
            service: service,
            fitStop: fitStop,
            fitService: fitService
        });

        self.map.on('zoomend zoomlevelschange', function() {
            if (self.map.getZoom() <= TILE_ZOOM) {
                self.stopLayer.removeAllTiles();
            } else {
                self.stopLayer.updateTiles();
            }
            self.update();
        });

        self.map.on('moveend', function() {
            self.stopLayer.updateTiles();
            self.setURL();
        });
    };

    /**
     * Starts up the map and adds map events
     * @param {object} options
     * @param {string} [options.stop] ATCO code for initial stop point
     * @param {string} [options.service] Initial service ID
     * @param {boolean} [options.reverse] Initial service direction
     * @param {number} [options.latitude] Starts map with latitude
     * @param {number} [options.longitude] Starts map with longitude
     * @param {number} [options.zoom] Starts map with zoom
     */
    this.init = function(options) {
        let mapOptions = {
            minZoom: MAP_ZOOM_MIN,
            maxZoom: MAP_ZOOM_MAX,
            maxBounds: L.latLngBounds(
                L.latLng(MAP_BOUNDS_NW),
                L.latLng(MAP_BOUNDS_SE)
            ),
            zoomControl: false
        };

        if (options && options.latitude && options.longitude && options.zoom) {
            // Go straight to specified coordinates & zoom
            mapOptions.center = L.latLng(options.latitude, options.longitude);
            mapOptions.zoom = options.zoom;
        } else if (!options || !options.stop && !options.service) {
            // Centre of GB map. If a service or stop is specified the coordinates and zoom are left
            // undefined until the route is loaded.
            mapOptions.center = L.latLng(MAP_CENTRE_GB);
            mapOptions.zoom = MAP_ZOOM_MIN;
        }

        // Create map
        self.map = L.map(self.mapContainer.id, mapOptions);
        self._addMapControls();

        // Set options for updating map - fit to stop or route if lat long zoom are not specified
        let fit = !(options.latitude && options.longitude && options.zoom),
            stop = options.stop,
            service;
        if (options && options.service) {
            service = {id: options.service, reverse: options.reverse}
        }

        if (options && options.service && options.stop) {
            let fitStop = null,
                fitService = null;

            // We want to wait for both stop and route to load before finishing init
            let finishInit = function() {
                if (fitStop != null && fitService != null) {
                    self._initComponents(stop, service, fitStop, fitService);
                }
            };

            self.stops.retrieve(stop, function() {
                fitStop = fit;
                finishInit();
            }, function(request) {
                console.debug('Problem with request for stop', stop, request);
                fitStop = false;
                finishInit();
            });

            self.services.retrieve(service, function() {
                self.routeLayer.set(service, false);
                fitService = false;
                finishInit();
            }, function(request) {
                console.debug('Problem with request for service', service, request);
                fitService = false;
                finishInit();
            });

        } else if (options && options.stop) {
            self.stops.retrieve(stop, function() {
                self._initComponents(stop, service, fit, false);
            }, function(request) {
                console.debug('Problem with request for stop', stop, request);
                self._initComponents(stop, service);
            });

        } else if (options && options.service) {
            self.services.retrieve(service, function() {
                self.routeLayer.set(service, fit);
                self._initComponents(stop, service, false, fit);
            }, function(request) {
                console.debug('Problem with request for service', service, request);
                self._initComponents(stop, service);
            });

        } else {
            self._initComponents(stop, service);
        }
    };

    /**
     * Updates map with a specified stop point with live times or a service diagram based on stops
     * @param {object} [options] Sets stop and service for map
     * @param {string} [options.stop] Sets stop (or removes if null) unless it is undefined
     * @param {ServiceID} [options.service] Sets service (or removes if null) unless it is undefined
     * @param {boolean} [options.fitService] Fit map to path bounds. True by default
     * @param {boolean} [options.fitStop] If setting a new stop, fit map to stop. False by default
     */
    this.update = function(options) {
        if (!options) {
            // Stop and route has not changed; update panel (eg new message at zoom level) and URL
            self.panel.updatePanel();
            self.setURL();
            return;
        }

        if (typeof options.stop !== 'undefined') {
            self.currentStop = options.stop;
        }
        if (typeof options.service !== 'undefined') {
            self.currentService = options.service;
        }

        let fitStop = options.stop && options.fitStop,
            fitService = options.service && options.fitService && !fitStop;

        if (self.currentStop && self.currentService) {
            let stopSet = false,
                routeSet = false,
                stopData,
                routeData;
            // We want both route and stop to load before finishing map update
            let finishUpdate = function() {
                if (stopSet && routeSet) {
                    if (fitStop) {
                        self.map.setView(L.latLng(stopData.latitude, stopData.longitude), 18);
                    }
                    self.routeLayer.set(self.currentService, fitService);
                    self.stopLayer.setStop(stopData);
                    self.stopLayer.setRoute(routeData);
                    self.panel.updatePanel();
                    self.setURL();
                }
            };

            self.stops.retrieve(self.currentStop, function(data) {
                stopSet = true;
                stopData = data;
                finishUpdate();
            });
            self.services.retrieve(self.currentService, function(data) {
                routeSet = true;
                routeData = data;
                finishUpdate();
            });

        } else if (self.currentStop) {
            // Unset any routes and load stop
            self.stops.retrieve(self.currentStop, function(data) {
                if (fitStop) {
                    self.map.setView(L.latLng(data.latitude, data.longitude), 18);
                }
                self.routeLayer.clear();
                self.stopLayer.setStop(data);
                self.stopLayer.removeRoute();
                self.panel.updatePanel();
                self.setURL();
            });

        } else if (self.currentService) {
            // Unset any current stops and return to original service, or set new service
            self.services.retrieve(self.currentService, function(data) {
                self.routeLayer.set(self.currentService, fitService);
                self.stopLayer.removeStop();
                self.stopLayer.setRoute(data);
                self.panel.updatePanel();
                self.setURL();
            });

        } else {
            // Unset both route and stop
            self.routeLayer.clear();
            self.stopLayer.removeStop();
            self.stopLayer.removeRoute();
            self.panel.updatePanel();
            self.setURL();
        }

    };

    // TODO: Can the page title be modified too?

    /**
     * Sets page to new URL with current stop, coordinates and zoom
     */
    this.setURL = function() {
        let routeURL = '',
            stopURL = '';

        if (self.routeLayer.data !== null) {
            let direction = (self.routeLayer.data.reverse) ? 'inbound' : 'outbound';
            routeURL = 'service/' + self.routeLayer.data.service + '/' + direction + '/';
        }
        if (self.stopLayer.data !== null) {
            stopURL = 'stop/' + self.stopLayer.data.atcoCode + '/';
        }

        let centre = self.map.getCenter(),
            zoom = self.map.getZoom(),
            accuracy = MAP_DEG_ACCURACY[zoom],
            coords = [roundTo(centre.lat, accuracy), roundTo(centre.lng, accuracy), zoom];

        let newURL = MAP_URL + routeURL + stopURL + coords.join(',');
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
    return command + ' ' + values.map(function(v) {
        return v.join(',');
    }).join(' ');
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
            y2: (r === self.data.length - 1) ?
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
        self.data.forEach(function (v) {
            let ind, colour;
            if (v.vertex !== null) {
                ind = document.getElementById('i' + v.vertex);
                colour = getComputedStyle(ind).backgroundColor;
            } else {
                ind = document.getElementById('iNull');
                colour = null;
            }
            self.listInd.push(ind);
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


/**
 * Draws diagram and add event listener to rebuild graph if required.
 * @param {(HTMLElement|string)} container DOM div node.
 * @param data Required data
 */
function setupGraph(container, data) {
    let containerElement = (container instanceof HTMLElement) ?
            container : document.getElementById(container);

    if (data == null) {
        return;
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
