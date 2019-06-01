/*
 * nxb functionality; copyright Ewan Macpherson 2017-19
 */

const INTERVAL = 90;

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
const LAYOUT_INVISIBLE = '#FFF0';
const LAYOUT_TIMEOUT = 500;

const LAYOUT_DOM_TEXT_START = 12;
const LAYOUT_DOM_DIV_START = 15;
const LAYOUT_DOM_PARA_START = 36 + 12;


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
 * Dialog / overlay handler. Thanks to https://bitsofco.de/accessible-modal-dialog/
 * @param {HTMLElement|string} overlayElement
 * @param {?HTMLElement|string} focusFirst
 * @constructor
 */
function Overlay(overlayElement, focusFirst) {
    let self = this;
    this.overlay = (overlayElement instanceof HTMLElement) ?
        overlayElement : document.getElementById(overlayElement);
    this.focusFirst = (focusFirst instanceof HTMLElement) ?
        focusFirst : document.getElementById(focusFirst);

    this.transition = getTransitionEnd(this.overlay);
    this.focusable = [];
    this.lastFocused = null;

    this.findFocusable = function() {
        self.focusable = Array.prototype.slice.call(
            self.overlay.querySelectorAll(
                'a[href], area[href], input:not([disabled]), select:not([disabled]), ' +
                'textarea:not([disabled]), button:not([disabled]), [tabindex="0"]'
            )
        );
    };
    this.findFocusable();

    /**
     * First focusable element.
     * @returns {HTMLElement}
     */
    this.first = function() {
        return self.focusable[0];
    };

    /**
     * Last focusable element.
     * @returns {HTMLElement}
     */
    this.last = function() {
        return self.focusable[self.focusable.length - 1];
    };

    /**
     * Takes keyboard event and ensures TAB returns back to focusable elements within overlay.
     * @private
     */
    this._cycleTabs = function(event) {
        const KEY_TAB = 'Tab';

        if (event.key === KEY_TAB && !event.shiftKey) {
            if (document.activeElement === self.last() ||
                self.focusable.indexOf(document.activeElement) === -1)
            {
                event.preventDefault();
                self.first().focus();
            }
        } else if (event.key === KEY_TAB) {
            if (document.activeElement === self.first() ||
                self.focusable.indexOf(document.activeElement) === -1)
            {
                event.preventDefault();
                self.last().focus();
            }
        }
    };

    /**
     * Handles TAB and ESC keyboard events for overlay.
     * @private
     */
    this._handleKeys = function(event) {
        const KEY_TAB = 'Tab',
              KEY_ESC = 'Escape';

        switch (event.key) {
            case KEY_TAB:
                self._cycleTabs(event);
                break;
            case KEY_ESC:
                self.close();
                break;
        }
    };

    /**
     * Called overlay finishes opening.
     * @callback overlayOpen
     */

    /**
     * Opens overlay and sets up keyboard events.
     * @param {overlayOpen} whenOpen
     */
    this.open = function(whenOpen) {
        self.lastFocused = document.activeElement;
        document.addEventListener('keydown', self._handleKeys);
        document.body.classList.add('body-with-overlay');
        self.overlay.classList.add('overlay-visible');
        if (whenOpen != null) {
            whenOpen();
        }
        if (self.focusFirst != null) {
            let onEndTransition = function() {
                self.overlay.removeEventListener(self.transition, onEndTransition);
                self.focusFirst.focus();
            };
            self.overlay.addEventListener(self.transition, onEndTransition);
        }
    };

    /**
     * Closes overlay and remove keyboard events.
     */
    this.close = function() {
        document.removeEventListener('keydown', self._handleKeys);
        document.body.classList.remove('body-with-overlay');
        self.overlay.classList.remove('overlay-visible');
        if (self.lastFocused != null) {
            self.lastFocused.focus();
        }
    }
}


/**
 * Sends requests to modify cookie data with list of starred stops
 * @constructor
 * @param {boolean} cookieSet Whether cookie has been set in first place or not
 */
function StarredStops(cookieSet) {
    let self = this;
    this.set = (typeof cookieSet !== 'undefined') ? cookieSet : true;
    this.onAdd = null;

    this.overlay = null;
    this.overlayElement = null;
    this.code = null;
    this.data = null;
    this.active = false;
    this.r = new XMLHttpRequest();

    this.setCode = function(code) {
        self.code = code;
    };

    this.createDialog = function() {
        if (self.overlayElement != null) {
            return;
        }
        self.overlayElement = element('div',
            {className: 'overlay', id: 'overlay-confirm'},
            element('div',
                {className: 'overlay-content overlay-content-dialog'},
                element('h3', 'Create a cookie?'),
                element('p',
                    'A new list of starred stops will be created on your device as a cookie. No ' +
                    'other identifiable information is stored.'
                ),
                element('button',
                    {id: 'cookie-reject', className: 'overlay-button',
                        title: 'Close this dialog and go back'},
                    'Close'
                ),
                element('button',
                    {id: 'cookie-confirm', className: 'overlay-button',
                        title: 'Create cookie and add stop'
                    },
                    'Continue adding stop'
                )
            )
        );
        document.body.appendChild(self.overlayElement);

        let confirm = document.getElementById('cookie-confirm'),
            reject = document.getElementById('cookie-reject');
        self.overlay = new Overlay(self.overlayElement, confirm);
        confirm.onclick = function() {
            self.overlay.close();
            self.set = true;
            self.add();
        };
        reject.onclick = function() {
            self.overlay.close();
        };
    };

    this.removeDialog = function() {
        if (self.overlayElement != null) {
            document.body.removeChild(self.overlayElement);
            self.overlayElement = null;
        }
    };

    /**
     * Called when starred stops API returns response.
     * @callback onLoad
     */

    /**
     * Gets list of stops and call function on load
     * @param {onLoad} onGet
     */
    this.get = function(onGet) {
        self.r.onload = function() {
            if (this.status === 200) {
                self.set = true;
                self.data = JSON.parse(self.r.responseText).stops;
            } else if (this.status === 422) {
                self.set = false;
                self.data = null;
            }
            onGet();
        };
        self.r.open('GET', URL.STARRED, true);
        self.r.send();
    };

    /**
     * Add stop to list and call function. If list not set, open overlay to confirm cookie before
     * continuing with callback.
     * @param {onLoad} onAdd
     */
    this.add = function(onAdd) {
        if (self.code == null) {
            throw new TypeError('SMS code needs to be set for StarredStops object first.');
        }
        if (!self.set && self.overlayElement == null) {
            self.createDialog();
        }
        if (!self.set) {
            // Save callback and reuse on next call
            self.onAdd = onAdd;
            self.overlay.open();
            return;
        }

        if (self.active) {
            return;
        }
        self.r.onload = function() {
            self.active = false;
            if (self.onAdd != null) {
                self.onAdd();
                self.onAdd = null;
            } else if (onAdd != null) {
                onAdd();
            }
        };
        self.r.open('POST', URL.STARRED + self.code, true);
        self.r.setRequestHeader('Content-type', 'application/x-www-form-urlencoded');
        self.r.send();
        self.active = true;
    };

    /**
     * Removes stop from list and call function.
     * @param {onLoad} onRemove
     */
    this.remove = function(onRemove) {
        if (self.code == null) {
            throw new TypeError('SMS code needs to be set for StarredStops object first.');
        }
        if (self.active || !self.set) {
            return;
        }
        self.r.onload = function() {
            self.active = false;
            if (onRemove != null) {
                onRemove();
            }
        };
        self.r.open('DELETE', URL.STARRED + self.code, true);
        self.r.setRequestHeader('Content-type', 'application/x-www-form-urlencoded');
        self.r.send();
        self.active = true;
    };
}


/**
 * Constructs a list of starred stops using the starred stops API
 * @param {HTMLElement|string} container Container element or ID for list of starred stops
 * @constructor
 */
function StarredStopList(container) {
    let self = this;
    this.container = (container instanceof HTMLElement) ?
        container : document.getElementById(container);
    this.map = null;
    this.overlay = null;
    this.called = false;

    /**
     * Sets list to use map such that clicking on starred stop item will update the map
     * @param {StopMap} map
     */
    this.setMap = function(map) {
        self.map = (map != null) ? map : null;
    };

    /**
     * Sets overlay so its focusable elements can be updated when the list is created
     * @param {Overlay} overlay
     */
    this.setOverlay = function(overlay) {
        self.overlay = (overlay != null) ? overlay : null;
    };

    /**
     * Sets to call API for updated list on next call
     */
    this.reset = function() {
        self.called = false;
    };

    /**
     * Calls API to get new list
     */
    this.updateList = function() {
        if (self.called) {
            return;
        }
        let request = new XMLHttpRequest();
        request.onload = function() {
            if (this.status === 200) {
                self._createList(JSON.parse(this.responseText));
                if (self.overlay != null) {
                    self.overlay.findFocusable();
                }
                self.called = true;
            } else if (this.status === 422) {
                // Cookie list does not exist yet; don't do any more calls until it has been reset
                self.called = true;
            }
        };
        request.open('GET', URL.STARRED + 'data', true);
        request.send();
    };

    /**
     * Constructs list of starred stops and replace contents of container
     * @param {{type: string, features: StopPoint[]}} data
     * @private
     */
    this._createList = function(data) {
        if (data.features.length === 0) {
            removeSubElements(self.container);
            return;
        }
        let heading = element('div',
            {className: 'h3-inline'},
            element('h3', 'Starred stops'),
            element('p',
                element('a',
                    {className: 'action', href: URL.STARRED_PAGE},
                    'Edit'
                )
            )
        );
        let list = element('ul', {className: 'list list-actions stops'});
        data.features.forEach(function(stop) {
            let sub = [stop.properties.street, stop.properties.locality].filter(function(p) {
                return p;
            });
            let item = element('a',
                {
                    className: 'item item-stop item-multiline',
                    href: URL.STOP_PAGE + stop.properties.atcoCode
                },
                element('span',
                    element('span',
                        {className: 'indicator area-' + stop.properties.adminAreaRef},
                        createIndicator(stop.properties)
                    ),
                    element('span', {className: 'item-label'}, stop.properties.name)
                ),
                (sub) ? element('p', sub.join(', ')) : null
            );
            let mapLink = element('a',
                {
                    className: 'item item-action',
                    innerHTML: '<svg class="icon" xmlns="http://www.w3.org/2000/svg" width="24" ' +
                        'height="24" viewBox="0 0 24 24"><path fill="none" d="M0 0h24v24H0V0z"/>' +
                        '<path class="icon-shape" d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 ' +
                        '13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 ' +
                        '0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 ' +
                        '2.5z"/></svg>'
                }
            );
            if (self.map != null) {
                mapLink.title = 'Go to stop ' + stop.properties.title + ' on map';
                mapLink.onclick = function() {
                    self.map.update({
                        stop: stop.properties.atcoCode,
                        fitStop: true,
                        service: null
                    });
                    if (self.overlay != null) {
                        self.overlay.close();
                    }
                };
            } else {
                mapLink.title = 'Go to map for ' + stop.properties.title;
                mapLink.href = URL.MAP + 'stop/' + stop.properties.atcoCode;
            }

            list.appendChild(element('li', item, mapLink));
        });

        removeSubElements(self.container);
        self.container.appendChild(heading);
        self.container.appendChild(list);
        resizeIndicator('.indicator');
    };
}


/**
 * Creates starred toggle button
 * @param {StarredStops} starred
 * @param {boolean} stopIsStarred
 * @param {StarredStopList} starredList
 * @returns {HTMLElement}
 */
function createStarredButton(starred, stopIsStarred, starredList) {
    let addText = '\u2606 Add stop',
        addTitle = 'Add to list of starred stops',
        removeText = '\u2605 Remove stop',
        removeTitle = 'Remove from list of starred stops';

    let starredButton = element('button');
    let onAdd, onRemove;

    onAdd = function() {
        starredButton.textContent = removeText;
        starredButton.title = removeTitle;
        starredButton.onclick = function() {
            starred.remove(onRemove);
        };
        if (starredList != null) {
            starredList.reset();
        }
    };
    onRemove = function() {
        starredButton.textContent = addText;
        starredButton.title = addTitle;
        starredButton.onclick = function() {
            starred.add(onAdd);
        };
        if (starredList != null) {
            starredList.reset();
        }
    };
    // Set up button
    (stopIsStarred) ? onAdd() : onRemove();

    return starredButton;
}


/**
 * @typedef {{
 *      label: string,
 *      value: string,
 *      disabled: boolean,
 *      selected: boolean,
 *      original: ?HTMLElement
 *  }} SelectOption
 */


/**
 * Creates a multiple selection which works better than the standard HTML element
 * @param {?HTMLElement|string} selectElement <select> element to replace
 * @param {?string} defaultText Text to display when no options are selected
 * @param {?function} onSelect Callback when an item is selected or deselected
 * @constructor
 */
function FilterList(selectElement, defaultText, onSelect) {
    let self = this;
    this.onSelect = (onSelect) ? onSelect : null;
    this.select = null;
    this.default = null;

    this.container = null;
    this.input = null;
    this.action = null;
    this.menu = null;

    /**
     * List of options
     * @type {SelectOption[]}
     */
    this.options = [];
    this.defaultItem = null;
    this.selectedItems = new Map();
    this.hidden = true;

    /**
     * Creates selected item
     * @param {SelectOption} option
     * @returns {HTMLElement}
     * @private
     */
    this._createSelected = function(option) {
        let item = element('a',
            {
                className: 'filter-selected',
                title: 'Remove ' + option.label + ' from filter',
                dataset: {value: option.value},
                tabIndex: '0'
            },
            option.label
        );
        if (option.disabled) {
            item.classList.add('filter-selected-disabled');
        } else {
            item.onclick = function() {
                self.removeItem(option);
            }
        }

        return item;
    };

    /**
     * Creates menu item
     * @param {SelectOption} option
     * @returns {HTMLElement}
     * @private
     */
    this._createItem = function(option) {
        let item = element('a',
            {
                className: 'filter-menu-item',
                title: 'Add ' + option.label + ' to filter',
                dataset: {value: option.value}
            },
            option.label
        );
        if (option.selected) {
            item.style.display = 'none';
        }
        if (option.disabled) {
            item.classList.add('filter-menu-item-disabled');
        } else {
            item.onclick = function() {
                self.addItem(option);
            }
        }

        return item;
    };

    this._updateDefault = function() {
        if (self.selectedItems.size === 0 && self.default != null) {
            self.defaultItem = element('span', {className: 'filter-default'}, self.default);
            self.input.appendChild(self.defaultItem);
        } else if (self.selectedItems.size > 0 && self.defaultItem != null) {
            self.input.removeChild(self.defaultItem);
            self.defaultItem = null;
        }
    };

    this._menuHeight = function() {
        let menuStyle = window.getComputedStyle(self.menu);
        let maxHeight = parseInt(menuStyle.maxHeight.match(/\d+/)[0]);

        return Math.min(self.menu.scrollHeight, maxHeight);
    };

    this._createList = function() {
        self.container = element('div', {className: 'filter-list'});
        window.addEventListener('click', function(event) {
            if (!self.hidden && !self.container.contains(event.target)) {
                self.hideMenu();
            }
        });

        self.input = element('div', {className: 'filter-input'});
        self.input.onclick = function() {
            if (self.hidden) {
                self.showMenu();
            }
        };

        self.menu = element('div',
            {className: 'filter-menu filter-menu-hidden', tabIndex: '-1'}
        );
        window.addEventListener('resize', function() {
            if (!self.hidden) {
                // Reset height, otherwise scrollHeight's value will just increase
                self.menu.style.height = 'auto';
                self.menu.style.height = self._menuHeight() + 'px';
            }
        });

        self.options.forEach(function(o) {
            let menuItem = self._createItem(o);
            self.menu.appendChild(menuItem);
            if (o.selected) {
                let selectedItem = self._createSelected(o);
                self.input.appendChild(selectedItem);
                self.selectedItems.set(o.value, selectedItem);
            }
        });
        self._updateDefault();

        self.container.appendChild(self.input);
        self.container.appendChild(self.menu);
        if (self.select != null) {
            // Hide original select element and replace
            self.select.style.display = 'none';
            self.select.parentNode.insertBefore(self.container, self.select.nextSibling);
        }
    };

    /**
     * Creates filter list from map
     * @param {Map<string, string>} map Map of values and labels
     * @param {?string} text Default text when no items selected
     */
    this.createFromMap = function(map, text) {
        self.select = null;
        self.default = (text != null) ? text : null;

        self.options = [];
        map.forEach(function(label, value) {
            self.options.push({
                label: label,
                value: value,
                disabled: false,
                selected: false,
                original: null
            });
        });

        self._createList();
    };

    /**
     * Creates filter list from existing <select> element
     * @param {HTMLElement|string} select Select element or ID
     * @param {?string} text Default text when no items selected
     */
    this.createFromSelect = function(select, text) {
        self.select = (select instanceof HTMLElement) ? select : document.getElementById(select);
        if (self.select.tagName !== 'SELECT' || !self.select.multiple) {
            throw new TypeError('Must be a select element with multiple options.');
        }
        self.default = (text != null) ? text : null;

        self.options = [];
        self.select.querySelectorAll('option').forEach(function(o) {
            self.options.push({
                label: o.label,
                value: o.value,
                disabled: o.disabled,
                selected: o.selected,
                original: o
            });
        });

        self._createList();
    };

    if (selectElement != null) {
        this.createFromSelect(selectElement, defaultText);
    }

    this._handleKeys = function(event) {
        const KEY_ESC = 'Escape';
        if (event.key === KEY_ESC) {
            self.hideMenu();
        }
    };

    /**
     * Shows menu
     */
    this.showMenu = function() {
        if (!self.hidden) {
            return;
        }
        if (self.selectedItems.size === self.options.length) {
            return;
        }
        self.hidden = false;

        self.menu.classList.remove('filter-menu-hidden');
        self.menu.style.height = self._menuHeight() + 'px';

        window.addEventListener('keydown', self._handleKeys);
    };

    /**
     * Hides menu
     */
    this.hideMenu = function() {
        if (self.hidden) {
            return;
        }
        self.hidden = true;

        self.menu.classList.add('filter-menu-hidden');
        self.menu.style.height = '0';

        window.removeEventListener('keydown', self._handleKeys);
    };

    /**
     * Selects an option. Updates original select element as well
     * @param {SelectOption} option
     */
    this.addItem = function(option) {
        if (option.selected) {
            return;
        }

        option.selected = true;
        if (option.original != null) {
            option.original.selected = true;
        }
        if (self.onSelect != null) {
            self.onSelect(self, option);
        }

        let selectedItem = self._createSelected(option),
            menuItem = self.menu.querySelector('a[data-value="' + option.value + '"]');
        self.selectedItems.set(option.value, selectedItem);
        self.input.appendChild(selectedItem);
        menuItem.style.display = 'none';
        self._updateDefault();

        if (self.selectedItems.size === self.options.length) {
            self.hideMenu();
        }
    };

    /**
     * Deselects an option. Updates original select element as well
     * @param {SelectOption} option
     */
    this.removeItem = function(option) {
        if (!option.selected) {
            return;
        }

        option.selected = false;
        if (option.original != null) {
            option.original.selected = false;
        }
        if (self.onSelect != null) {
            self.onSelect(self, option);
        }

        let menuItem = self.menu.querySelector('a[data-value="' + option.value + '"]');
        self.input.removeChild(self.selectedItems.get(option.value));
        self.selectedItems.delete(option.value);
        menuItem.style.display = '';
        self._updateDefault();
    };
}


function _resizeText(element) {
    if (element.dataset.indicatorSet != null) {
        return;
    }
    // Set data attribute and add class
    element.dataset.indicatorSet = '1';
    let span = element.querySelector('span');
    let img = element.querySelector('img');
    if (span !== null) {
        let ind = span.textContent;
        let len = ind.replace(/(&#?\w+;)/, ' ').length;
        switch (len) {
            case 1:
                element.classList.add('indicator-1');
                break;
            case 2:
                // Text 'WW' is as wide as most 3-character strings
                element.classList.add((ind === 'WW') ? 'indicator-3' : 'indicator-2');
                break;
            case 3:
                element.classList.add('indicator-3');
                break;
            case 4:
                element.classList.add('indicator-4');
                break;
        }
        // Use font's arrow symbol instead of '->'
        span.textContent = span.textContent.replace('->', '→');
    } else if (img !== null) {
        let style = window.getComputedStyle(element);
        let fontSize = parseFloat(style.fontSize);
        img.width = Math.round(2.8 * fontSize);
    }
}


/**
 * Resize text within indicators so they look better. Elements have a data attribute set so they can
 * be skipped the next time this function is called.
 * @param {string} selectors Argument for querySelectorAll
 */
function resizeIndicator(selectors) {
    document.querySelectorAll(selectors).forEach(_resizeText);
}


function _revertColours(element) {
    if (element.dataset.coloursSet != null) {
        // Already covered previously; skip over
        return;
    }
    // Set data attribute and add class
    element.dataset.coloursSet = '1';
    let style = window.getComputedStyle(element);
    let foreground = style.getPropertyValue('color');
    let background = style.getPropertyValue('background-color');
    element.style.backgroundColor = foreground;
    element.style.color = background;
}


/**
 * Reverts colours of indicators
 * @param {string} selectors Argument for querySelectorAll
 */
function revertColours(selectors) {
    document.querySelectorAll(selectors).forEach(_revertColours)
}


/**
 * Shorthand for creating a new element without namespace
 * @param {string} tag tag name
 * @param {?(object|HTMLElement|string|(HTMLElement|string)[])} [attr] object to set DOM attributes
 * for new element, eg style. If attribute 'attr' is specified it can be used to set HTML attributes
 * for element manually which can't be done with DOM element attributes, eg 'aria-label'. Can also
 * be first child element or array of children if no attributes are required
 * @param  {...?(HTMLElement|string|(HTMLElement|string)[])} children child elements or array of
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
        let k, v, s;
        for (k in attr) {
            if (!attr.hasOwnProperty(k)) {
                continue;
            }
            v = attr[k];
            if (k === 'attr') {
                for (s in v) {
                    if (v.hasOwnProperty(s)) {
                        element.setAttribute(s, v[s]);
                    }
                }
            } else if (k === 'dataset') {
                for (s in v) {
                    if (v.hasOwnProperty(s)) {
                        element.dataset[s] = v[s];
                    }
                }
            } else if (k === 'style') {
                for (s in v) {
                    if (v.hasOwnProperty(s)) {
                        element.style[s] = v[s];
                    }
                }
            } else {
                element[k] = v;
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
 * @param {{code: string, name: string}[]} [operators] Optional list of operators
 * @param {?(HTMLElement|string)} container Table container element or ID in document
 * @param {?(HTMLElement|string)} time Element or ID in document showing time when data was
 * retrieved
 * @param {?(HTMLElement|string)} countdown Element or ID in document showing time before next
 * refresh
 */
function LiveData(atcoCode, adminAreaCode, operators, container, time, countdown) {
    let self = this;
    this.atcoCode = atcoCode;
    this.adminAreaCode = adminAreaCode;
    this.url = URL.LIVE;
    this.container = null;
    this.headingTime = null;
    this.headingCountdown = null;
    this.operators = null;
    if (operators) {
        self.operators = new Map();
        operators.forEach(function(o) {
            self.operators.set(o.code, o.name);
        });
    }

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
     * Sets container, heading with time and subheading with countdown to specified elements
     * @param {(HTMLElement|string)} container
     * @param {(HTMLElement|string)} time
     * @param {(HTMLElement|string)} countdown
     */
    this.setElements = function(container, time, countdown) {
        self.container = (container instanceof HTMLElement) ?
            container : document.getElementById(container);
        self.headingTime = (time instanceof HTMLElement) ? time : document.getElementById(time);
        self.headingCountdown = (countdown instanceof HTMLElement) ?
            countdown : document.getElementById(countdown);
    };

    if (container != null && time != null && countdown != null) {
        this.setElements(container, time, countdown);
    }

    /**
     * Called after live data is successfully received.
     * @callback afterLiveData
     * @param {string} atcoCode
     */

    /**
     * Gets data from server, refreshing table
     * @param {afterLiveData} [after] Callback to be used upon successful request
     */
    this.get = function(after) {
        self.headingTime.textContent = 'Updating...';
        let request = new XMLHttpRequest();
        request.open('GET', self.url + self.atcoCode, true);
        request.setRequestHeader('Content-Type', 'charset=utf-8');

        request.onreadystatechange = function() {
            if (request.readyState !== XMLHttpRequest.DONE) {
                return;
            }
            if (request.status === 200) {
                self.data = JSON.parse(request.responseText);
                self.isLive = true;
                self.draw();
            } else if (self.data != null) {
                self.isLive = false;
                self.draw();
            } else {
                self.isLive = false;
                self.headingTime.textContent = 'No data available';
            }
            if (typeof after !== 'undefined') {
                after(self.atcoCode);
            }
        };

        request.send();
    };

    /**
     * Refreshes table with new data
     */
    this.draw = function() {
        if (!self.isLive) {
            self.estimate();
        }
        if (self.data != null && self.data.services.length > 0) {
            self._drawTable();
        } else if (self.data != null) {
            self._drawEmpty();
        } else {
            self.headingTime.textContent = 'Updating...';
            console.debug('No data received yet when printed for stop ' + self.atcoCode);
        }
    };

    /**
     * Gets class name for this journey
     * @param {boolean} isLive Whether this particular journey is tracked or not
     * @private
     */
    this._classLive = function(isLive) {
        return (!isLive) ? '' : (self.isLive) ? 'departure-live' : 'departure-estimated';
    };

    /**
     * Draws table from data
     * @private
     */
    this._drawTable = function() {
        let message = (self.isLive) ? 'Live times at ' : 'Estimated times from ';
        self.headingTime.textContent = message + self.data.localTime;

        let table = element('table', {className: 'departures'});
        for (let s = 0; s < self.data.services.length; s++) {
            let service = self.data.services[s];
            let first = service.expected[0],
                departures = Math.min(service.expected.length, 5),
                times = [],
                timesAfter = [];

            times.push(element('span',
                {className: self._classLive(first.live)},
                (first.secs < 90) ? 'due' : Math.round(first.secs / 60) + ' min'
            ));

            for (let n = 1; n < departures; n++) {
                let expected = service.expected[n],
                    fromEnd = departures - n,
                    minutes = Math.round(expected.secs / 60) +
                        ((fromEnd > 2) ? ',' : (fromEnd > 1) ? ' and' : ' min');
                timesAfter.push(element('span',
                    {className: self._classLive(expected.live)},
                    minutes
                ));
                if (fromEnd > 1) {
                    timesAfter.push(' ');
                }
            }
            if (timesAfter.length > 0) {
                times.push(element('br'));
                times.push(element('span', timesAfter));
            }

            let row = element('tr',
                element('td',
                    element('span',
                        {className: 'line-outer'},
                        element('span',
                            {className: 'line area-' + self.adminAreaCode},
                            element('span', service.name)
                        )
                    )
                ),
                element('td', service.dest),
                element('td', service.opCode),
                element('td', self.operators.get(service.opCode) || service.opName || null),
                element('td', times)
            );

            table.appendChild(row);
        }
        // Remove all existing elements
        removeSubElements(self.container);
        // Add table
        self.container.appendChild(table);
        console.debug('Created table with ' + self.data.services.length +
                        ' services for stop "' + self.atcoCode + '".');
    };

    /**
     * No data received, so display a message
     * @private
     */
    this._drawEmpty = function() {
        removeSubElements(self.container);
        if (self.isLive) {
            self.headingTime.textContent = 'No services expected at ' + self.data.localTime;
        } else {
            self.headingTime.textContent = 'No services found';
        }
        console.debug('No services found for stop ' + self.atcoCode + '.');
    };

    /**
     * Updates seconds remaining with current date/time if no data received
     */
    this.estimate = function() {
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
                    s.expected.splice(j, 1);
                }
            }
            if (s.expected.length === 0) {
                self.data.services.splice(i, 1);
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
    this.start = function(callbacks) {
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
            self.draw();
            return;
        }

        self.get(onStart);

        let time = INTERVAL;
        self.loopActive = true;
        self.interval = setInterval(function() {
            time--;
            self.headingCountdown.textContent = (time > 0) ? time : 'now';
            if (time <= 0) {
                if (self.loopEnding) {
                    self.headingCountdown.textContent = '';
                    self.loopActive = false;
                    self.loopEnding = false;
                    clearInterval(self.interval);
                    if (typeof onEnd !== 'undefined') {
                        onEnd(self.atcoCode);
                    }
                } else {
                    self.get(onInter);
                    time = INTERVAL;
                }
            }
        }, 1000);
    };

    /**
     * Sets the loop to not repeat after it runs out. Can be restarted with start() again
     */
    this.stop = function() {
        if (self.loopActive) {
            self.loopEnding = true;
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
 * @param {{action: function, content: ?Element|string, className: ?string, title: ?string}} actions
 */
function mapControl(...actions) {
    let buttons = actions.map(function(a) {
        let titleText = (a.title != null) ? a.title : '';
        let className = (a.className != null) ? a.className : '';
        return element('a',
            {role: 'button', title: titleText, 'aria-label': titleText, className: className,
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
 *     terminates: boolean,
 *     operators: string[]
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
 *     active: boolean,
 *     adminArea: {code: string, name: string},
 *     district: ?{code: string, name: string},
 *     locality: {code: string, name: string},
 *     services: StopServiceData[],
 *     operators: {code: string, name: string}[]
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
        ind = element('img', {src: URL.STATIC + 'img/bus-white.svg', width: '28', alt: 'Bus stop'});
    } else if (stopData.stopType === 'PLT') {
        ind = element('img', {src: URL.STATIC + 'img/tram-white.svg', width: '28', alt: 'Tram stop'});
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

    /**
     * Data for current stop.
     * @type {?StopPointData}
     */
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
                resizeIndicator('.indicator-marker');
            }
            return;
        }

        let url = URL.TILE + coords.x + ',' + coords.y;
        let request = new XMLHttpRequest;
        request.open('GET', url, true);

        request.onload = function() {
            let data = JSON.parse(request.responseText);
            if (data.features.length > 0) {
                let layer = self.createLayer(data);
                self.loadedTiles.set(key, {coords: coords, layer: layer});
                self.layers.addLayer(layer);
                resizeIndicator('.indicator-marker');
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
            resizeIndicator('.indicator-marker');
        }
    };

    /**
     * Creates marker element to be used in map
     * @param {StopPoint} stop Point object from data
     * @returns {HTMLElement} Element for marker
     * @private
     */
    this._markerElement = function(stop) {
        let className = 'indicator indicator-marker area-' + stop.properties.adminAreaRef;
        if (!self.isIE && stop.properties.bearing) {
            className += ' ' + 'indicator-arrow indicator-arrow-' + stop.properties.bearing;
        }
        return element('span',
            {className: className},
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
        request.open('GET', URL.STOP + atcoCode, true);
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
        request.open('GET', URL.ROUTE + part, true);
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
    this.layer = null;

    /**
     * Data for current stop.
     * @type {?ServiceData}
     */
    this.data = null;

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
 * @param {StarredStops} starred starred stops interface
 * @param {StarredStopList} starredList starred stops interface
 */
function Panel(stopMap, mapPanel, starred, starredList) {
    let self = this;
    this.stopMap = stopMap;
    this.mapPanel = mapPanel;
    this.container = this.mapPanel.parentNode;

    this.starred = starred;
    this.starred.createDialog();
    this.starredList = starredList;

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
     * @param {{code: string, name: string}[]} operators List of operators
     */
    this.getStop = function(atcoCode, adminAreaRef, table, time, countdown, operators) {
        let live;
        if (!self.activeStops.has(atcoCode)) {
            live = new LiveData(
                atcoCode,
                adminAreaRef,
                operators,
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
        live.start({
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
                data.stop();
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
        let heading = element('h2', headingText);

        self.clearPanel();
        self.mapPanel.appendChild(heading);
    };


    /**
     * Sets panel for bus stop live data and other associated info
     * @param {StopPointData} data Data for stop point, locality and services
     * @private
     */
    this._setStopPanelData = function(data) {
        let leaveTitle, leaveText;
        if (self.currentService !== null) {
            let data = self.stopMap.routeLayer.data;
            leaveTitle = 'Back to service ' + data.line;
            leaveText = '\u2191 Back';
        } else {
            leaveTitle = 'Close stop panel';
            leaveText = '\u2717 Close';
        }
        let closePanel = element('button',
            {
                title: leaveTitle,
                onclick: function() {
                    this.blur();
                    self.stopMap.update({stop: null});
                    return false;
                }
            },
            leaveText
        );
        let actions = element('div', {className: 'actions'}, closePanel);

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

        let heading = element('h1',
                {className: 'heading-stop'},
                element('span',
                    {className: 'indicator area-' + data.adminAreaRef},
                    createIndicator(data)
                ),
                element('span', data.name),
        );

        let liveTimes = element('section',
            element('div',
                {className: 'h2-inline'},
                element('h2', {id: 'live-time'}, 'Retrieving live data...'),
                element('p', {id: 'live-countdown', class: 'countdown'})
            ),
            element('div', {id: 'departures', class: 'departures-container'})
        );

        let services = element('section', element('h2', 'Services'));
        if (data.services.length > 0) {
            let listNonTerminating = [],
                listTerminating = [];
            data.services.forEach(function(s) {
                let listItem = element('li',
                    element('div',
                        {className: 'item item-service', onclick: function() {
                            self.stopMap.update({
                                stop: null,
                                service: {id: s.id, reverse: s.reverse},
                                fitService: true
                            });
                        }},
                        element('span',
                            {className: 'line-outer'},
                            element('span',
                                {className: 'line area-' + data.adminAreaRef},
                                s.line
                            )
                        ),
                        element('div',
                            {className: 'item-label'},
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
            element('h2', 'Stop information'),
            infoLine,
            element('p', 'SMS code ', element('strong', data.naptanCode)),
            (data.active) ?
                null : element('p', element('strong', 'This stop is marked as inactive.')),
            element('p', element('a', {href: URL.STOP_PAGE + data.atcoCode}, 'Stop page'))
        );

        self.clearPanel();
        self.mapPanel.appendChild(heading);
        self.mapPanel.appendChild(headingText);
        self.mapPanel.appendChild(actions);
        self.mapPanel.appendChild(liveTimes);
        self.mapPanel.appendChild(services);
        self.mapPanel.appendChild(stopInfo);
        resizeIndicator('.indicator');

        self.getStop(
            data.atcoCode,
            data.adminAreaRef,
            'departures',
            'live-time',
            'live-countdown',
            data.operators
        );

        self.starred.setCode(data.naptanCode);
        self.starred.get(function() {
            let codeInList = (self.starred.set && self.starred.data.indexOf(data.naptanCode) > -1);
            let button = createStarredButton(self.starred, codeInList, self.starredList);
            actions.insertBefore(button, closePanel);
        });

        // Add control for zooming into stop view
        self.currentMapControl = mapControl({
            action: function() {
                self.stopMap.map.flyTo(L.latLng(data.latitude, data.longitude), 18);
            },
            className: 'icon-fit-map',
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
        let closePanel = element('button',
            {
                title: 'Close service panel',
                onclick: function() {
                    this.blur();
                    self.stopMap.update({service: null});
                }
            },
            '\u2717 Close'
        );
        let direction = (data.reverse) ? 'inbound' : 'outbound',
            timetableURL = URL.TIMETABLE.replace('//', '/' + data.service + '/' + direction + '/');
        let timetable = element('a',
            {className: 'action', href: timetableURL, title: data.line + ' timetable'},
            'Timetable'
        );
        let actions = element('div', {className: 'actions'}, timetable, closePanel);

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

        let heading = element('h1',
            {className: 'heading-service'},
            element('span',
                {className: 'line-outer'},
                element('span',
                    {className: 'line'},
                    data.line
                )
            ),
            element('span', data.description)
        );
        let subtitle = element('p', 'Operated by ', listOperators);

        let tabs = null;
        if (data.mirrored) {
            tabs = element('ul',
                {className: 'tabs tabs-2'},
                element('li',
                    element('div',
                        {className: (data.reverse) ? 'tab' : 'tab tab-active',
                         onclick: (data.reverse) ? function() {
                             map.update({service: {id: data.service, reverse: false}});
                         } : null},
                        'Outbound'
                    )
                ),
                element('li',
                    element('div',
                        {className: (data.reverse) ? 'tab tab-active' : 'tab',
                         onclick: (data.reverse) ? null : function() {
                             map.update({service: {id: data.service, reverse: true}});
                         }},
                        'Inbound'
                    )
                )
            );
        }

        let list = element('section', {style: {position: 'relative'}}),
            diagram = element('div', {className: 'diagram'});

        let listStops = null;
        if (data.sequence) {
            listStops = element('ul', {className: 'list list-relative'});
            data.sequence.forEach(function(code) {
                let s = data.stops[code],
                    item;
                if (code) {
                    item = element('div',
                        {className: 'item item-stop item-service-stop'}
                    );

                    let sub = [s.properties.street, s.properties.locality].filter(function (p) {
                        return p;
                    });
                    let subtitle = (sub) ? element('p', sub.join(', ')) : null;

                    let inner = element('span',
                        {id: 'c' + s.properties.atcoCode, className: 'item-multiline'},
                        element('span',
                            element('span',
                                {className: 'indicator area-' + s.properties.adminAreaRef,
                                 id: 'i' + s.properties.atcoCode},
                                createIndicator(s.properties)
                            ),
                            element('span', {className: 'item-label'}, s.properties.name),
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
                        {className: 'item item-stop item-service-stop item-service-stop-empty'},
                        element('span',
                            {id: 'cNull'},
                            element('span', {className: 'indicator', id: 'iNull'})
                        )
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
        self.mapPanel.appendChild(heading);
        self.mapPanel.appendChild(subtitle);
        self.mapPanel.appendChild(actions);
        if (tabs) {
            self.mapPanel.appendChild(tabs);
        }
        self.mapPanel.appendChild(list);

        // Add control for fitting service to map
        self.currentMapControl = mapControl({
            action: function() {
                self.stopMap.map.fitBounds(self.stopMap.routeLayer.layer.getBounds());
            },
            className: 'icon-fit-map',
            title: 'Fit route to map'
        });
        self.currentMapControl.addTo(self.stopMap.map);

        if (data.stops) {
            resizeIndicator('.indicator');
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


// TODO: iOS Safari in landscape: live stop panel keeps jumping up to front when countdown updated
// TODO: SVG diagram extends past bottom of list into footer. Can an extra row be added?


/**
 * Handles the map container and stops
 * @constructor
 * @param {string} mapContainer ID for map container element
 * @param {string} mapPanel ID for map panel element
 * @param {StarredStops} starred Starred stops interface
 * @param {StarredStopList} starredList Starred stop list for overlay
 * @param {boolean} useGeolocation Enable geolocation on this map
 */
function StopMap(mapContainer, mapPanel, starred, starredList, useGeolocation) {
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

    this.panel = new Panel(this, this.mapPanel, starred, starredList);
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
                let container = element(
                    'div',
                    {className: 'leaflet-control-zoom leaflet-bar leaflet-control-custom'}
                );

                this._zoomInButton  = this._createButton('', this.options.zoomInTitle,
                    'leaflet-control-zoom-in icon-zoom-in', container, this._zoomIn);
                this._zoomOutButton = this._createButton('', this.options.zoomOutTitle,
                    'leaflet-control-zoom-out icon-zoom-out', container, this._zoomOut);

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
                className: 'icon-my-location',
                title: 'Find your location on map'
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
        let andFinally = function() {
            self.panel.updatePanel();
            self.setURL();
            self.setTitle();
        };

        if (!options) {
            // Stop and route has not changed
            andFinally();
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
                    andFinally();
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
                andFinally();
            });

        } else if (self.currentService) {
            // Unset any current stops and return to original service, or set new service
            self.services.retrieve(self.currentService, function(data) {
                self.routeLayer.set(self.currentService, fitService);
                self.stopLayer.removeStop();
                self.stopLayer.setRoute(data);
                andFinally();
            });

        } else {
            // Unset both route and stop
            self.routeLayer.clear();
            self.stopLayer.removeStop();
            self.stopLayer.removeRoute();
            andFinally();
        }

    };

    /**
     * Updates title with current stop or route
     */
    this.setTitle = function() {
        let routeData = self.routeLayer.data,
            stopData = self.stopLayer.data;
        let components = ['Map'];

        if (stopData != null) {
            components.push(self.stopLayer.data.title);
        } else if (routeData != null) {
            components.push(routeData.line + ': ' + routeData.description);
        }
        components.push('nxb');
        let title = components.join(' – ');

        if (title !== document.title) {
            document.title = title;
        }
    };

    /**
     * Sets page to new URL with current stop, coordinates and zoom
     */
    this.setURL = function() {
        let routeData = self.routeLayer.data,
            stopData = self.stopLayer.data;
        let routeURL = '',
            stopURL = '';

        if (routeData != null) {
            let direction = (routeData.reverse) ? 'inbound' : 'outbound';
            routeURL = 'service/' + routeData.service + '/' + direction + '/';
        }
        if (stopData != null) {
            stopURL = 'stop/' + stopData.atcoCode + '/';
        }

        let centre = self.map.getCenter(),
            zoom = self.map.getZoom(),
            accuracy = MAP_DEG_ACCURACY[zoom],
            coords = [roundTo(centre.lat, accuracy), roundTo(centre.lng, accuracy), zoom];

        let newURL = URL.MAP + routeURL + stopURL + coords.join(',');
        history.replaceState(null, null, newURL);
    };
}


/**
 * Returns a SVG element with specified attributes
 * @param {string} tag SVG element tag
 * @param {object} [attr] Attributes for element
 * @returns {SVGElement}
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
    let text = container.querySelector('.item-label'),
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
