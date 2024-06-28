from __future__ import annotations

import dataclasses as dc
import datetime as dt
import typing as t

from dataclasses_json import DataClassJsonMixin

# LEFT="⬅️"
# RIGHT="➡️"

_OCLOCK = ["🕛", "🕐", "🕑", "🕒", "🕓", "🕔", "🕕", "🕖", "🕗", "🕘", "🕙", "🕚"]
_THIRTY = ["🕧", "🕜", "🕝", "🕞", "🕟", "🕠", "🕡", "🕢", "🕣", "🕤", "🕥", "🕦"]

_FLAGS = {
    v.lower(): k
    for k, vs in {
        "🇦🇨": ["AC", "Ascension Island"],
        "🇦🇩": ["AD", "Andorra"],
        "🇦🇪": ["AE", "United Arab Emirates"],
        "🇦🇫": ["AF", "Afghanistan"],
        "🇦🇬": ["AG", "Antigua and Barbuda", "Antigua & Barbuda"],
        "🇦🇮": ["AI", "Anguilla"],
        "🇦🇱": ["AL", "Albania"],
        "🇦🇲": ["AM", "Armenia"],
        "🇦🇴": ["AO", "Angola"],
        "🇦🇶": ["AQ", "Antarctica"],
        "🇦🇷": ["AR", "Argentina"],
        "🇦🇸": ["AS", "American Samoa"],
        "🇦🇹": ["AT", "Austria"],
        "🇦🇺": ["AU", "Australia"],
        "🇦🇼": ["AW", "Aruba"],
        "🇦🇽": ["AX", "Åland Islands"],
        "🇦🇿": ["AZ", "Azerbaijan"],
        "🇧🇦": ["BA", "Bosnia and Herzegovina", "Bosnia & Herzegovina"],
        "🇧🇧": ["BB", "Barbados"],
        "🇧🇩": ["BD", "Bangladesh"],
        "🇧🇪": ["BE", "Belgium"],
        "🇧🇫": ["BF", "Burkina Faso"],
        "🇧🇬": ["BG", "Bulgaria"],
        "🇧🇭": ["BH", "Bahrain"],
        "🇧🇮": ["BI", "Burundi"],
        "🇧🇯": ["BJ", "Benin"],
        "🇧🇱": ["BL", "Saint Barthélemy", "St. Barthélemy"],
        "🇧🇲": ["BM", "Bermuda"],
        "🇧🇳": ["BN", "Brunei"],
        "🇧🇴": ["BO", "Bolivia"],
        "🇧🇶": ["BQ", "Caribbean Netherlands"],
        "🇧🇷": ["BR", "Brazil"],
        "🇧🇸": ["BS", "The Bahamas", "Bahamas"],
        "🇧🇹": ["BT", "Bhutan"],
        "🇧🇻": ["BV", "Bouvet Island"],
        "🇧🇼": ["BW", "Botswana"],
        "🇧🇾": ["BY", "Belarus"],
        "🇧🇿": ["BZ", "Belize"],
        "🇨🇦": ["CA", "Canada"],
        "🇨🇨": ["CC", "Cocos (Keeling) Islands"],
        "🇨🇩": ["CD", "Democratic Republic of the Congo", "Congo - Kinshasa"],
        "🇨🇫": ["CF", "Central African Republic"],
        "🇨🇬": ["CG", "Republic of the Congo", "Congo - Brazzaville"],
        "🇨🇭": ["CH", "Switzerland"],
        "🇨🇮": ["CI", "Ivory Coast", "Côte d'Ivoire"],
        "🇨🇰": ["CK", "Cook Islands"],
        "🇨🇱": ["CL", "Chile"],
        "🇨🇲": ["CM", "Cameroon"],
        "🇨🇳": ["CN", "China"],
        "🇨🇴": ["CO", "Colombia"],
        "🇨🇵": ["CP", "Clipperton Island"],
        "🇨🇷": ["CR", "Costa Rica"],
        "🇨🇺": ["CU", "Cuba"],
        "🇨🇻": ["CV", "Cape Verde"],
        "🇨🇼": ["CW", "Curaçao"],
        "🇨🇽": ["CX", "Christmas Island"],
        "🇨🇾": ["CY", "Cyprus"],
        "🇨🇿": ["CZ", "Czech Republic", "Czechia"],
        "🇩🇪": ["DE", "Germany"],
        "🇩🇬": ["DG", "Diego Garcia"],
        "🇩🇯": ["DJ", "Djibouti"],
        "🇩🇰": ["DK", "Denmark"],
        "🇩🇲": ["DM", "Dominica"],
        "🇩🇴": ["DO", "Dominican Republic"],
        "🇩🇿": ["DZ", "Algeria"],
        "🇪🇦": ["EA", "Ceuta"],
        "🇪🇨": ["EC", "Ecuador"],
        "🇪🇪": ["EE", "Estonia"],
        "🇪🇬": ["EG", "Egypt"],
        "🇪🇭": ["EH", "Western Sahara"],
        "🇪🇷": ["ER", "Eritrea"],
        "🇪🇸": ["ES", "Spain"],
        "🇪🇹": ["ET", "Ethiopia"],
        "🇪🇺": ["EU", "European Union"],
        "🇫🇮": ["FI", "Finland"],
        "🇫🇯": ["FJ", "Fiji"],
        "🇫🇰": ["FK", "Falkland Islands"],
        "🇫🇲": ["FM", "Federated States of Micronesia", "Micronesia"],
        "🇫🇴": ["FO", "Faroe Islands"],
        "🇫🇷": ["FR", "France"],
        "🇬🇦": ["GA", "Gabon"],
        "🇬🇧": ["GB", "United Kingdom"],
        "🇬🇩": ["GD", "Grenada"],
        "🇬🇪": ["GE", "Georgia (country)", "Georgia"],
        "🇬🇫": ["GF", "French Guiana"],
        "🇬🇬": ["GG", "Guernsey"],
        "🇬🇭": ["GH", "Ghana"],
        "🇬🇮": ["GI", "Gibraltar"],
        "🇬🇱": ["GL", "Greenland"],
        "🇬🇲": ["GM", "Gambia"],
        "🇬🇳": ["GN", "Guinea"],
        "🇬🇵": ["GP", "Guadeloupe"],
        "🇬🇶": ["GQ", "Equatorial Guinea"],
        "🇬🇷": ["GR", "Greece"],
        "🇬🇸": [
            "GS",
            "South Georgia and the South Sandwich Islands",
            "South Georgia & South Sandwich Islands",
        ],
        "🇬🇹": ["GT", "Guatemala"],
        "🇬🇺": ["GU", "Guam"],
        "🇬🇼": ["GW", "Guinea-Bissau"],
        "🇬🇾": ["GY", "Guyana"],
        "🇭🇰": ["HK", "Hong Kong"],
        "🇭🇲": ["HM", "Heard Island and McDonald Islands", "Heard & McDonald Islands"],
        "🇭🇳": ["HN", "Honduras"],
        "🇭🇷": ["HR", "Croatia"],
        "🇭🇹": ["HT", "Haiti"],
        "🇭🇺": ["HU", "Hungary"],
        "🇮🇨": ["IC", "Canary Islands"],
        "🇮🇩": ["ID", "Indonesia"],
        "🇮🇪": ["IE", "Republic of Ireland", "Ireland"],
        "🇮🇱": ["IL", "Israel"],
        "🇮🇲": ["IM", "Isle of Man"],
        "🇮🇳": ["IN", "India"],
        "🇮🇴": ["IO", "British Indian Ocean Territory"],
        "🇮🇶": ["IQ", "Iraq"],
        "🇮🇷": ["IR", "Iran"],
        "🇮🇸": ["IS", "Iceland"],
        "🇮🇹": ["IT", "Italy"],
        "🇯🇪": ["JE", "Jersey"],
        "🇯🇲": ["JM", "Jamaica"],
        "🇯🇴": ["JO", "Jordan"],
        "🇯🇵": ["JP", "Japan"],
        "🇰🇪": ["KE", "Kenya"],
        "🇰🇬": ["KG", "Kyrgyzstan"],
        "🇰🇭": ["KH", "Cambodia"],
        "🇰🇮": ["KI", "Kiribati"],
        "🇰🇲": ["KM", "Comoros"],
        "🇰🇳": ["KN", "Saint Kitts and Nevis", "St. Kitts & Nevis"],
        "🇰🇵": ["KP", "North Korea"],
        "🇰🇷": ["KR", "South Korea"],
        "🇰🇼": ["KW", "Kuwait"],
        "🇰🇾": ["KY", "Cayman Islands"],
        "🇰🇿": ["KZ", "Kazakhstan"],
        "🇱🇦": ["LA", "Laos"],
        "🇱🇧": ["LB", "Lebanon"],
        "🇱🇨": ["LC", "Saint Lucia", "St. Lucia"],
        "🇱🇮": ["LI", "Liechtenstein"],
        "🇱🇰": ["LK", "Sri Lanka"],
        "🇱🇷": ["LR", "Liberia"],
        "🇱🇸": ["LS", "Lesotho"],
        "🇱🇹": ["LT", "Lithuania"],
        "🇱🇺": ["LU", "Luxembourg"],
        "🇱🇻": ["LV", "Latvia"],
        "🇱🇾": ["LY", "Libya"],
        "🇲🇦": ["MA", "Morocco"],
        "🇲🇨": ["MC", "Monaco"],
        "🇲🇩": ["MD", "Moldova"],
        "🇲🇪": ["ME", "Montenegro"],
        "🇲🇫": ["MF", "Collectivity of Saint Martin", "St. Martin"],
        "🇲🇬": ["MG", "Madagascar"],
        "🇲🇭": ["MH", "Marshall Islands"],
        "🇲🇰": ["MK", "North Macedonia"],
        "🇲🇱": ["ML", "Mali"],
        "🇲🇲": ["MM", "Myanmar", "Myanmar (Burma)"],
        "🇲🇳": ["MN", "Mongolia"],
        "🇲🇴": ["MO", "Macau", "Macao SAR China"],
        "🇲🇵": ["MP", "Northern Mariana Islands"],
        "🇲🇶": ["MQ", "Martinique"],
        "🇲🇷": ["MR", "Mauritania"],
        "🇲🇸": ["MS", "Montserrat"],
        "🇲🇹": ["MT", "Malta"],
        "🇲🇺": ["MU", "Mauritius"],
        "🇲🇻": ["MV", "Maldives"],
        "🇲🇼": ["MW", "Malawi"],
        "🇲🇽": ["MX", "Mexico"],
        "🇲🇾": ["MY", "Malaysia"],
        "🇲🇿": ["MZ", "Mozambique"],
        "🇳🇦": ["NA", "Namibia"],
        "🇳🇨": ["NC", "New Caledonia"],
        "🇳🇪": ["NE", "Niger"],
        "🇳🇫": ["NF", "Norfolk Island"],
        "🇳🇬": ["NG", "Nigeria"],
        "🇳🇮": ["NI", "Nicaragua"],
        "🇳🇱": ["NL", "Netherlands"],
        "🇳🇴": ["NO", "Norway"],
        "🇳🇵": ["NP", "Nepal"],
        "🇳🇷": ["NR", "Nauru"],
        "🇳🇺": ["NU", "Niue"],
        "🇳🇿": ["NZ", "New Zealand"],
        "🇴🇲": ["OM", "Oman"],
        "🇵🇦": ["PA", "Panama"],
        "🇵🇪": ["PE", "Peru"],
        "🇵🇫": ["PF", "French Polynesia"],
        "🇵🇬": ["PG", "Papua New Guinea"],
        "🇵🇭": ["PH", "Philippines"],
        "🇵🇰": ["PK", "Pakistan"],
        "🇵🇱": ["PL", "Poland"],
        "🇵🇲": ["PM", "Saint Pierre and Miquelon", "St. Pierre & Miquelon"],
        "🇵🇳": ["PN", "Pitcairn Islands"],
        "🇵🇷": ["PR", "Puerto Rico"],
        "🇵🇸": ["PS", "Palestinian territories", "Palestinian Territories"],
        "🇵🇹": ["PT", "Portugal"],
        "🇵🇼": ["PW", "Palau"],
        "🇵🇾": ["PY", "Paraguay"],
        "🇶🇦": ["QA", "Qatar"],
        "🇷🇪": ["RE", "Réunion"],
        "🇷🇴": ["RO", "Romania"],
        "🇷🇸": ["RS", "Serbia"],
        "🇷🇺": ["RU", "Russia"],
        "🇷🇼": ["RW", "Rwanda"],
        "🇸🇦": ["SA", "Saudi Arabia"],
        "🇸🇧": ["SB", "Solomon Islands"],
        "🇸🇨": ["SC", "Seychelles"],
        "🇸🇩": ["SD", "Sudan"],
        "🇸🇪": ["SE", "Sweden"],
        "🇸🇬": ["SG", "Singapore"],
        "🇸🇭": ["SH", "Saint Helena", "St. Helena"],
        "🇸🇮": ["SI", "Slovenia"],
        "🇸🇯": ["SJ", "Svalbard and Jan Mayen", "Svalbard & Jan Mayen"],
        "🇸🇰": ["SK", "Slovakia"],
        "🇸🇱": ["SL", "Sierra Leone"],
        "🇸🇲": ["SM", "San Marino"],
        "🇸🇳": ["SN", "Senegal"],
        "🇸🇴": ["SO", "Somalia"],
        "🇸🇷": ["SR", "Suriname"],
        "🇸🇸": ["SS", "South Sudan"],
        "🇸🇹": ["ST", "São Tomé and Príncipe", "São Tomé & Príncipe"],
        "🇸🇻": ["SV", "El Salvador"],
        "🇸🇽": ["SX", "Sint Maarten"],
        "🇸🇾": ["SY", "Syria"],
        "🇸🇿": ["SZ", "Eswatini"],
        "🇹🇦": ["TA", "Tristan da Cunha"],
        "🇹🇨": ["TC", "Turks and Caicos Islands", "Turks & Caicos Islands"],
        "🇹🇩": ["TD", "Chad"],
        "🇹🇫": ["TF", "French Southern and Antarctic Lands", "French Southern Territories"],
        "🇹🇬": ["TG", "Togo"],
        "🇹🇭": ["TH", "Thailand"],
        "🇹🇯": ["TJ", "Tajikistan"],
        "🇹🇰": ["TK", "Tokelau"],
        "🇹🇱": ["TL", "East Timor", "Timor-Leste"],
        "🇹🇲": ["TM", "Turkmenistan"],
        "🇹🇳": ["TN", "Tunisia"],
        "🇹🇴": ["TO", "Tonga"],
        "🇹🇷": ["TR", "Turkey", "Türkiye"],
        "🇹🇹": ["TT", "Trinidad and Tobago", "Trinidad & Tobago"],
        "🇹🇻": ["TV", "Tuvalu"],
        "🇹🇼": ["TW", "Taiwan"],
        "🇹🇿": ["TZ", "Tanzania"],
        "🇺🇦": ["UA", "Ukraine"],
        "🇺🇬": ["UG", "Uganda"],
        "🇺🇲": ["UM", "United States Minor Outlying Islands", "U.S. Outlying Islands"],
        "🇺🇳": ["UN", "United Nations"],
        "🇺🇸": ["US", "United States"],
        "🇺🇾": ["UY", "Uruguay"],
        "🇺🇿": ["UZ", "Uzbekistan"],
        "🇻🇦": ["VA", "Vatican City"],
        "🇻🇨": ["VC", "Saint Vincent and the Grenadines", "St. Vincent & Grenadines"],
        "🇻🇪": ["VE", "Venezuela"],
        "🇻🇬": ["VG", "British Virgin Islands"],
        "🇻🇮": ["VI", "United States Virgin Islands", "U.S. Virgin Islands"],
        "🇻🇳": ["VN", "Vietnam"],
        "🇻🇺": ["VU", "Vanuatu"],
        "🇼🇫": ["WF", "Wallis and Futuna", "Wallis & Futuna"],
        "🇼🇸": ["WS", "Samoa"],
        "🇽🇰": ["XK", "Kosovo"],
        "🇾🇪": ["YE", "Yemen"],
        "🇾🇹": ["YT", "Mayotte"],
        "🇿🇦": ["ZA", "South Africa"],
        "🇿🇲": ["ZM", "Zambia"],
        "🇿🇼": ["ZW", "Zimbabwe"],
    }.items()
    for v in vs
}


@dc.dataclass
class UnicodeEmojiData(DataClassJsonMixin):
    clocks_oh: t.List[str]  # noqa: F841
    clocks_thirty: t.List[str]  # noqa: F841
    flags: t.Dict[str, str]  # noqa: F841

    @staticmethod
    def create() -> UnicodeEmojiData:
        return UnicodeEmojiData(
            _OCLOCK,
            _THIRTY,
            _FLAGS,
        )


def append_flag(country: str) -> str:
    flag_ = _FLAGS.get(country.lower())
    if flag_ is not None:
        return f"{country}{flag_}"
    return country


def replace_with_flag(country: str) -> str:
    return _FLAGS.get(country.lower(), country)


def flag(country: str) -> t.Optional[str]:
    return _FLAGS.get(country.lower())


def maybe_datetime_to_clock(value: t.Optional[dt.datetime]) -> t.Optional[str]:
    if value is None:
        return None
    if value.minute < 30:
        mapping = _OCLOCK
    else:
        mapping = _THIRTY
    return mapping[value.hour % 12]