#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

import os, sys, pwd, subprocess, re, argparse
from datetime import datetime

from pyasn1_modules import pem, rfc2459
from pyasn1.codec.der import decoder
from pyasn1.type.univ import OctetString

import yaml

CONF_FILE = '/etc/letsencrypt/renew.yaml'
RE_CERTIFICATE_FILENAME = re.compile(r'^(\d+)_cert.crt$')

def parse_certificate(certificate_path):
    fqdns = set()

    substrate = pem.readPemFromFile(open(certificate_path))
    cert = decoder.decode(substrate, asn1Spec=rfc2459.Certificate())[0]
    core = cert['tbsCertificate']

    # Extract CommonName
    for rdnss in core['subject']:
        for rdns in rdnss:
            for name in rdns:
                if name.getComponentByName('type') == rfc2459.id_at_commonName:
                    value = decoder.decode(name.getComponentByName('value'), asn1Spec=rfc2459.DirectoryString())[0]
                    fqdns.add(str(value.getComponent()))

    # extract notAfter datetime
    notAfter = str(core['validity'].getComponentByName('notAfter').getComponent()).strip('Z')
    (year, month, day, hour, minute, seconds) = [int(notAfter[i:i+2]) for i in range(0, len(notAfter), 2)]
    expiration_date = datetime(2000 + year, month, day, hour, minute, seconds)

    # Extract SubjectAltName
    for extension in core['extensions']:
        if extension['extnID'] == rfc2459.id_ce_subjectAltName:
            octet_string = decoder.decode(extension.getComponentByName('extnValue'), asn1Spec=OctetString())[0]
            (san_list, r) = decoder.decode(octet_string, rfc2459.SubjectAltName())
            for san_struct in san_list:
                if san_struct.getName() == 'dNSName':
                    fqdns.add(str(san_struct.getComponent()))
    return (fqdns, expiration_date)

def renew_certificate(cn, webroot, fqdns, working_dir, admin_email, staging = False, verbose = False):
    cert_symlink = 'latest_cert.crt'
    chain_symlink = 'latest_chain.pem'
    fullchain_symlink = 'latest_fullchain.pem'

    os.chdir(working_dir)
    latest = os.readlink(cert_symlink)
    serial = int(RE_CERTIFICATE_FILENAME.match(latest).group(1))

    new_cert = '{:04d}_cert.crt'.format(serial + 1)
    new_fullchain = '{:04d}_fullchain.pem'.format(serial + 1)
    new_chain = '{:04d}_chain.pem'.format(serial + 1)

    command = ['certbot', 'certonly', '-n', '-q', 
            '--webroot', '-w', webroot,
            ]
    for fqdn in fqdns:
        command.extend(['-d', fqdn])
    command.extend(['--email', admin_email, 
            '--csr', os.path.join(working_dir, cn + '.csr'),
            '--cert-path', os.path.join(working_dir, new_cert),
            '--fullchain-path', os.path.join(working_dir, new_fullchain),
            '--chain-path', os.path.join(working_dir, new_chain),
            ])
    if staging:
        command.extend(['--staging', '--break-my-certs'])
    if verbose:
        subprocess.call(['echo'] + command)
    ret_code = subprocess.call(command)
    if verbose:
        print(ret_code)

    if ret_code == 0:
        if os.path.exists(new_cert):
            if os.path.exists(cert_symlink):
                os.remove(cert_symlink)
            os.symlink(new_cert, cert_symlink)
        if os.path.exists(new_chain):
            if os.path.exists(chain_symlink):
                os.remove(chain_symlink)
            os.symlink(new_chain, chain_symlink)
        if os.path.exists(new_fullchain):
            if os.path.exists(fullchain_symlink):
                os.remove(fullchain_symlink)
            os.symlink(new_fullchain, fullchain_symlink)

def restart_daemons(daemons, verbose = False):
    for daemon in daemons:
        command = ['systemctl', daemon['action'], daemon['name']]
        if verbose:
            subprocess.call(['echo'] + command)
        ret_code = subprocess.call(command)
        if verbose:
            print(ret_code)

def handle_certificates(cert_root, www_root, threshold, daemons, admin_email, staging = False, verbose = False):
    will_restart_daemons = False
    for site in os.listdir(cert_root):
        if verbose:
            print('Evaluating', site)

        site_path = os.path.join(cert_root, site)
        owner = pwd.getpwuid(os.stat(site_path).st_uid).pw_name
        webroot = os.path.join(www_root, owner, site)
        cert_path = os.path.join(site_path, 'latest_cert.crt')

        if os.path.exists(cert_path):
            (fqdns, expiration_date) = parse_certificate(cert_path)
            if verbose:
                print(fqdns)

            now = datetime.now()
            delta = expiration_date - now
            if now >= expiration_date or delta.days <= threshold:
                if verbose:
                    print('Renewing, expired or expires in', delta.days, 'days, less than', threshold)
                renew_certificate(site, webroot, fqdns, site_path, admin_email, staging, verbose)
                will_restart_daemons = True
    if will_restart_daemons:
        restart_daemons(daemons, verbose)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-v', '--verbose', action='store_true', help='talk more')
    parser.add_argument('-s', '--staging', action='store_true', 
            help='issue staging certificates (useful for testing purposes)')
    parser.add_argument('-c', '--config', default=CONF_FILE, 
            help='path to a config file (default: {})'.format(CONF_FILE))
    args = parser.parse_args()
    config = yaml.load(open(args.config))

    handle_certificates(config['certs_root'], config['www_root'], config['threshold'], config['daemons'], 
            config['admin_email'], staging=args.staging, verbose=args.verbose)
