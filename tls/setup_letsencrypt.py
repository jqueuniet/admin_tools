#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

import os, sys, pwd, grp, subprocess, argparse, tempfile
import yaml

CONF_FILE = '/etc/letsencrypt/setup.yaml'

def setup_env(certs_root, cn, owner, verbose = False):
    path = os.path.join(certs_root, cn)
    pw_owner = pwd.getpwnam(owner)
    grp_sslcert = grp.getgrnam('ssl-cert')

    os.makedirs(path)
    os.chown(path, pw_owner.pw_uid, grp_sslcert.gr_gid)

def create_private_key(certs_root, cn, keytype = 'ecdsa', verbose = False):
    if keytype == 'ecdsa':
        key_path = os.path.join(certs_root, cn, '{}-secp384r1.key'.format(cn))
        command = ['openssl', 'ecparam', '-genkey', '-name', 'secp384r1', '-out', key_path]
    else:
        print('Type de clé inconnu:', keytype, file=sys.stderr)
        sys.exit(1)

    if verbose:
        subprocess.call(['echo'] + command)
    ret_code = subprocess.call(command)
    return key_path

def create_certificate_request(certs_root, cn, fqdns, key_path, verbose = False):
    (fh, temp_conf) = tempfile.mkstemp()
    csr_path = os.path.join(certs_root, cn, '{}.csr'.format(cn))

    san = ','.join(['DNS:' + an for an in fqdns])
    with open('/etc/ssl/openssl.cnf') as openssl_fh:
        with open(temp_conf, 'w') as tp_fh:
            tp_fh.write(openssl_fh.read())
            print("[SAN]\nsubjectAltName={}".format(san), file=tp_fh)

    command = ['openssl', 'req', '-new', '-sha256', '-key', key_path, '-subj', '/CN={}'.format(cn), 
            '-reqexts', 'SAN', '-config', temp_conf, '-outform', 'PEM', '-out', csr_path
            ]

    if verbose:
        subprocess.call(['echo'] + command)
    ret_code = subprocess.call(command)
    os.unlink(temp_conf)
    return csr_path

def apply_for_certificate(certs_root, www_root, owner, cn, fqdns, csr_path, admin_email, 
        staging = False, verbose = False):
    cert_symlink = 'latest_cert.crt'
    chain_symlink = 'latest_chain.pem'
    fullchain_symlink = 'latest_fullchain.pem'

    new_cert = '0000_cert.crt'
    new_fullchain = '0000_fullchain.pem'
    new_chain = '0000_chain.pem'

    webroot = os.path.join(www_root, owner, cn)

    os.chdir(os.path.join(certs_root, cn))

    command = ['certbot', 'certonly', '-n', '-q',
            '--webroot', '-w', webroot, '--agree-tos',
            ]
    for fqdn in fqdns:
        command.extend(['-d', fqdn])
    command.extend(['--email', admin_email,
            '--csr', csr_path,
            '--cert-path', os.path.join(certs_root, cn, new_cert),
            '--fullchain-path', os.path.join(certs_root, cn, new_fullchain),
            '--chain-path', os.path.join(certs_root, cn, new_chain),
            ])
    if staging:
        command.extend(['--staging', '--break-my-certs'])
    if verbose:
        subprocess.call(['echo'] + command)
    ret_code = subprocess.call(command)

    if ret_code == 0:
        if os.path.exists(new_cert):
            os.symlink(new_cert, cert_symlink)
        if os.path.exists(new_chain):
            os.symlink(new_chain, chain_symlink)
        if os.path.exists(new_fullchain):
            os.symlink(new_fullchain, fullchain_symlink)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('cn', help='main FQDN, used as CommonName')
    parser.add_argument('owner', help='system user affiliated with certificate')
    parser.add_argument('-v', '--verbose', action='store_true', help='talk more')
    parser.add_argument('-s', '--staging', action='store_true',
            help='issue staging certificates (useful for testing purposes)')
    parser.add_argument('-k', '--keytype', default='ecdsa',
            help='type of private key (either rsa or ecdsa, default: ecdsa)')
    parser.add_argument('-a', '--altnames', default=None,
            help='aliases for the certificate, used as SubjectAltName')
    parser.add_argument('-c', '--config', default=CONF_FILE,
            help='path to a config file (default: {})'.format(CONF_FILE))
    args = parser.parse_args()
    config = yaml.load(open(args.config))

    if args.altnames:
        fqdns = set([args.cn] + args.altnames.split(','))
    else:
        fqdns = [args.cn]

    setup_env(config['certs_root'], args.cn, args.owner, args.verbose)
    key_path = create_private_key(config['certs_root'], args.cn, args.keytype, args.verbose)
    csr_path = create_certificate_request(config['certs_root'], args.cn, fqdns, key_path, args.verbose)
    apply_for_certificate(config['certs_root'], config['www_root'], args.owner, args.cn, fqdns, csr_path, 
        config['admin_email'], staging=args.staging, verbose=args.verbose)
