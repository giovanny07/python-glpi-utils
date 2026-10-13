<?php
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2025-2026 Giovanny Rodriguez, Imagunet
//
// Creates an OAuth client for integration tests (GLPI 11+) and prints
// "<client_id> <client_secret>". Run inside the GLPI container from the
// GLPI root as the web server user.
//
// redirect_uri, grants and scopes are passed as PHP arrays: add() encodes
// them; passing JSON strings double-encodes them and breaks /api.php/token.

require './vendor/autoload.php';

$kernel = new \Glpi\Kernel\Kernel('production');
$kernel->boot();
\Session::initEntityProfiles(2);

$client = new OAuthClient();
$id = $client->add([
    'name'            => 'glpi-utils-integration',
    'redirect_uri'    => ['/api.php/oauth2/redirection'],
    'grants'          => ['password', 'client_credentials', 'authorization_code'],
    'scopes'          => ['api', 'user', 'email', 'status', 'graphql'],
    'is_active'       => 1,
    'is_confidential' => 1,
]);
$client->getFromDB($id);
echo $client->fields['identifier'], ' ', (new GLPIKey())->decrypt($client->fields['secret']), PHP_EOL;
