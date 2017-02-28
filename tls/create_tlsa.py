#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

import os, sys, hashlib, argparse

from pyasn1_modules import pem, rfc2459
from pyasn1.codec.der import decoder, encoder
from pyasn1.type.univ import OctetString

def parse_certificate(certificate_path):
    fqdns = set()

    substrate = pem.readPemFromFile(open(certificate_path))
    cert = decoder.decode(substrate, asn1Spec=rfc2459.Certificate())[0]
    core = cert['tbsCertificate']

    # Hash public key
    der = encoder.encode(core.getComponentByName('subjectPublicKeyInfo'))
    hash_der = hashlib.sha256()
    hash_der.update(der)
    pkhash = hash_der.hexdigest()

    # Extract CommonName
    for rdnss in core['subject']:
        for rdns in rdnss:
            for name in rdns:
                if name.getComponentByName('type') == rfc2459.id_at_commonName:
                    value = decoder.decode(name.getComponentByName('value'), asn1Spec=rfc2459.DirectoryString())[0]
                    fqdns.add(str(value.getComponent()))

    # Extract SubjectAltName
    for extension in core['extensions']:
        if extension['extnID'] == rfc2459.id_ce_subjectAltName:
            octet_string = decoder.decode(extension.getComponentByName('extnValue'), asn1Spec=OctetString())[0]
            (san_list, r) = decoder.decode(octet_string, rfc2459.SubjectAltName())
            for san_struct in san_list:
                if san_struct.getName() == 'dNSName':
                    fqdns.add(str(san_struct.getComponent()))
    return (pkhash, fqdns)

def create_tlsa(certificate_path, stream, port):
    (pkhash, fqdns) = parse_certificate(certificate_path)
    for fqdn in fqdns:
        print('_{}._{}.{}   IN  TLSA    3 1 1 {}'.format(port, stream, fqdn, pkhash))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('certificate', help='path to certificate')
    parser.add_argument('stream', default='tcp', help='stream type (eg: tcp, udp), default to tcp')
    parser.add_argument('port', default='443', help='network port, default to 443')
    args = parser.parse_args()
    create_tlsa(args.certificate, args.stream, args.port)
