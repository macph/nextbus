"""
Populating database with data from NPTG, NaPTAN and NSPL.
"""
import click
import csv
import json
import lxml.etree as et
import os.path

from definitions import ROOT_DIR
from nextbus import app, db, models

# TODO: What about dates; when was the data last updated?
# TODO: Data sources - APIs and downloaded files. wget, requests or urllib?
# TODO: Get ability to update data; compare dates, check if data is same


def _xpath_text(element, path, namespaces=None):
    """ Takes the first node from list provided by an element's XPath query and
        returns the text value.
    """
    list_nodes = element.xpath(path, namespaces=namespaces)
    elements = len(list_nodes)
    if elements == 1:
        return list_nodes[0].text
    elif elements > 1:
        raise ValueError("Multiple elements matching XPath query.")
    else:
        return None


def _xpath_args(data, namespace, dict_args):
    """ Returns a new dict with XPath queries for all arguments. """
    return {k: _xpath_text(data, v, namespace) for k, v in dict_args.items()}


def _progress_bar(iterable, **kwargs):
    """ Returns click.progressbar with specific options. """
    return click.progressbar(
        iterable=iterable,
        bar_template="%(label)-32s [%(bar)s] %(info)s",
        show_pos=True,
        width=64,
        **kwargs
    )


def commit_naptan_data(atco_codes=None, nptg_file=None, naptan_file=None):
    """ Convert NPTG data (regions admin areas, districts and localities) and
        NaPTAN data (stop points and areas) to database objects and commit them
        to the application database.
    """
    click.echo("Opening files %r and %r..." % (nptg_file, naptan_file))
    nptg_data = et.parse(nptg_file)
    naptan_data = et.parse(naptan_file)
    ns = {'n': nptg_data.xpath("namespace-uri(.)"),
          's': naptan_data.xpath("namespace-uri(.)")}
    filter_atco_codes = bool(atco_codes)

    if filter_atco_codes:
        # Filter lists of regions, admin areas and localities
        list_admin_areas = []
        invalid_codes = []
        for code in atco_codes:
            area = nptg_data.xpath("//n:AdministrativeArea"
                                   "[n:AtcoAreaCode='%d']" % code,
                                   namespaces=ns)
            if area:
                list_admin_areas.append(area[0])
            else:
                invalid_codes.append(code)
        if invalid_codes:
            raise click.BadOptionUsage("The following ATCO codes cannot be found:\n"
                                       ", ".join(repr(i) for i in invalid_codes))

        list_aa_codes = [_xpath_text(aa, "n:AdministrativeAreaCode", ns)
                         for aa in list_admin_areas]
        aa_query = ' or '.join(f".='{a}'" for a in list_aa_codes)
        list_regions = nptg_data.xpath("n:Regions/n:Region"
                                       "[.//n:AdministrativeAreaCode[%s]]" % aa_query,
                                       namespaces=ns)
        list_districts = nptg_data.xpath("n:Regions//n:AdministrativeArea"
                                         "[n:AdministrativeAreaCode[%s]]"
                                         "//n:NptgDistrict" % aa_query, namespaces=ns)
        list_localities = nptg_data.xpath("n:NptgLocalities/n:NptgLocality"
                                          "[n:AdministrativeAreaRef[%s]]" % aa_query,
                                          namespaces=ns)
        list_locality_codes = [_xpath_text(l, "n:NptgLocalityCode", ns)
                               for l in list_localities]
    else:
        # Just find all regions, admin areas and localities
        list_admin_areas = nptg_data.xpath("n:Regions//n:AdministrativeArea", namespaces=ns)
        list_regions = nptg_data.xpath("n:Regions/n:Region", namespaces=ns)
        list_districts = nptg_data.xpath("n:Regions//n:NptgDistrict", namespaces=ns)
        list_localities = nptg_data.xpath("n:NptgLocalities/n:NptgLocality", namespaces=ns)
        list_locality_codes = []

    list_objects = []
    region_paths = {
        "region_code":          "n:RegionCode",
        "region_name":          "n:Name",
        "country":              "n:Country"
    }
    area_paths = {
        "admin_area_code":      "n:AdministrativeAreaCode",
        "region_code":          "ancestor::n:Region/n:RegionCode",
        "atco_area_code":       "n:AtcoAreaCode",
        "area_name":            "n:Name",
        "area_short_name":      "n:ShortName"
    }
    district_paths = {
        "nptg_district_code":   "n:NptgDistrictCode",
        "admin_area_code":      "ancestor::n:AdministrativeArea/n:AdministrativeAreaCode",
        "district_name":        "n:Name"
    }
    locality_paths = {
        "nptg_locality_code":   "n:NptgLocalityCode",
        "locality_name":        "n:Descriptor/n:LocalityName",
        "admin_area_code":      "n:AdministrativeAreaRef",
        "nptg_district_code":   "n:NptgDistrictRef",
        "easting":              "n:Location/n:Translation/n:Easting",
        "northing":             "n:Location/n:Translation/n:Northing",
        "longitude":            "n:Location/n:Translation/n:Longitude",
        "latitude":             "n:Location/n:Translation/n:Latitude"
    }

    with _progress_bar(list_regions, label="Parsing NPTG regions") as iter_regions:
        for region in iter_regions:
            obj_region = models.Region(**_xpath_args(region, ns, region_paths))
            list_objects.append(obj_region)

    with _progress_bar(list_admin_areas, label="Parsing NPTG admin areas") as iter_areas:
        for area in iter_areas:
            obj_area = models.AdminArea(**_xpath_args(area, ns, area_paths))
            list_objects.append(obj_area)

    with _progress_bar(list_districts, label="Parsing NPTG districts") as iter_districts:
        for district in iter_districts:
            obj_district = models.District(**_xpath_args(district, ns, district_paths))
            list_objects.append(obj_district)

    with _progress_bar(list_localities, label="Parsing NPTG localities") as iter_localities:
        for locality in iter_localities:
            obj_locality = models.Locality(**_xpath_args(locality, ns, locality_paths))
            list_objects.append(obj_locality)

    # Filter by admin area code for XPath queries if required
    if filter_atco_codes:
        # add 147 for trams
        list_aa_codes = [_xpath_text(aa, "n:AdministrativeAreaCode", ns)
                         for aa in list_admin_areas]
        list_aa_codes.append('147')
        aa_query = ' or '.join(".='%s'" % a for a in list_aa_codes)
        q = "(s:AdministrativeAreaRef[%s])" % aa_query + ' and '
    else:
        q = ''

    # Put together XPath queries - filter to active stops and of certain types
    l1 = ' or '.join(".='%s'" % t for t in ['BCT', 'BCS', 'PLT'])
    stop_point_path = ("s:StopPoints/s:StopPoint"
                       "[@Status='active']"
                       "[%s(s:StopClassification/s:StopType[%s])]" % (q, l1))
    stop_points = naptan_data.xpath(stop_point_path, namespaces=ns)

    l2 = ' or '.join(".='%s'" % t for t in ['GBPS', 'GCLS', 'GBCS', 'GTMU'])
    stop_area_path = ("s:StopAreas/s:StopArea"
                      "[@Status='active']"
                      "[%s(s:StopAreaType[%s])]" % (q, l2))
    stop_areas = naptan_data.xpath(stop_area_path, namespaces=ns)

    stop_point_paths = {
        "atco_code":            "s:AtcoCode",
        "naptan_code":          "s:NaptanCode",
        "desc_common":          "s:Descriptor/s:CommonName",
        "desc_short":           "s:Descriptor/s:ShortCommonName",
        "desc_landmark":        "s:Descriptor/s:Landmark",
        "desc_street":          "s:Descriptor/s:Street",
        "desc_crossing":        "s:Descriptor/s:Crossing",
        "desc_indicator":       "s:Descriptor/s:Indicator",
        "nptg_locality_code":   "s:Place/s:NptgLocalityRef",
        "suburb":               "s:Place/s:Suburb",
        "town":                 "s:Place/s:Town",
        "easting":              "s:Place/s:Location/s:Translation/s:Easting",
        "northing":             "s:Place/s:Location/s:Translation/s:Northing",
        "longitude":            "s:Place/s:Location/s:Translation/s:Longitude",
        "latitude":             "s:Place/s:Location/s:Translation/s:Latitude",
        "stop_type":            "s:StopClassification/s:StopType",
        "bearing":              ".//s:CompassPoint",
        "stop_area_code":       "s:StopAreas/s:StopAreaRef",
        "admin_area_code":      "s:AdministrativeAreaRef"
    }
    stop_area_paths = {
        "stop_area_code":       "s:StopAreaCode",
        "stop_area_name":       "s:Name",
        "admin_area_code":      "s:AdministrativeAreaRef",
        "stop_area_type":       "s:StopAreaType",
        "easting":              "s:Location/s:Translation/s:Easting",
        "northing":             "s:Location/s:Translation/s:Northing",
        "longitude":            "s:Location/s:Translation/s:Longitude",
        "latitude":             "s:Location/s:Translation/s:Latitude"
    }
    # Want all points and areas that are active
    set_stop_area_codes = set([])
    with _progress_bar(stop_points, label="Parsing NaPTAN stop points") as iter_points:
        for point in iter_points:
            if filter_atco_codes and (_xpath_text(point, "s:Place/s:NptgLocalityRef", ns)
                                      not in list_locality_codes):
                # Skip over if filtering by ATCO area code
                continue
            if _xpath_text(point, "s:NaptanCode", ns) is None:
                # Skip over if stop point does not have a NaPTAN code
                continue
            obj_point = models.StopPoint(**_xpath_args(point, ns, stop_point_paths))
            # Get all stop areas that satisfy above conditions
            set_stop_area_codes.add(_xpath_text(point, stop_point_paths["stop_area_code"], ns))
            list_objects.append(obj_point)

    with _progress_bar(stop_areas, label="Parsing NaPTAN stop areas") as iter_areas:
        for area in iter_areas:
            if filter_atco_codes and (_xpath_text(area, "s:StopAreaCode", ns)
                                      not in set_stop_area_codes):
                # Skip over
                continue
            obj_area = models.StopArea(**_xpath_args(area, ns, stop_area_paths))
            list_objects.append(obj_area)

    click.echo("Adding %d objects..." % len(list_objects))
    db.session.add_all(list_objects)
    click.echo("Committing changes to database...")
    db.session.commit()


def commit_nspl_data(atco_codes=None, nspl_file=None, token=None):
    """ Converts NSPL data (postcodes) to database objects and commit them
        to the working database.
    """
    la_file = os.path.join(ROOT_DIR, "nextbus/local_authority_list.json")
    with open(la_file, 'r') as jf:
        data = json.load(jf)
    filter_atco_codes = bool(atco_codes)

    if filter_atco_codes:
        dict_la = {loc_auth.pop("la_code"): loc_auth for loc_auth in data
                   if loc_auth["admin_area_code"] in atco_codes}
    else:
        dict_la = {loc_auth.pop("la_code"): loc_auth for loc_auth in data}

    click.echo("Opening file %r..." % nspl_file)
    cf = open(nspl_file, 'r')
    # Find number of rows in CSV file
    len_lines = sum(1 for r in csv.reader(cf)) - 1
    # reset read location
    cf.seek(0)

    list_postcodes = []
    with _progress_bar(csv.DictReader(cf), label="Parsing postcode data",
                       length=len_lines) as iter_postcodes:
        for row in iter_postcodes:
            if filter_atco_codes and row["Local Authority Code"] not in dict_la:
                # Filter by ATCO area code if it applies
                continue
            if row["Country Code"] not in ['E92000001', 'S92000003', 'W92000004']:
                # Don't need NI, IoM or the Channel Islands
                continue
            if row["Positional Quality"] in [8, 9]:
                # Low accuracy; just skip row
                continue
            local_authority = dict_la[row["Local Authority Code"]]
            postcode = models.Postcode(
                postcode=row["Postcode 3"],
                postcode_2=''.join(row["Postcode 3"].split()),
                local_authority_code=row["Local Authority Code"],
                admin_area_code=local_authority["admin_area_code"],
                easting=row["Easting"],
                northing=row["Northing"],
                longitude=row["Longitude"],
                latitude=row["Latitude"]
            )
            list_postcodes.append(postcode)
    cf.close()

    click.echo("Adding %d postcodes..." % len(list_postcodes))
    db.session.add_all(list_postcodes)
    click.echo("Committing changes to database...")
    db.session.commit()


if __name__ == "__main__":
    NAPTAN = os.path.join(ROOT_DIR, "temp/data/Naptan.xml")
    NPTG = os.path.join(ROOT_DIR, "temp/data/NPTG.xml")
    NSPL = os.path.join(ROOT_DIR, "temp/data/nspl.csv")
    with app.app_context():
        commit_naptan_data(nptg_file=NPTG, naptan_file=NAPTAN)
        commit_nspl_data(nspl_file=NSPL)
