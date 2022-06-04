
aws secretsmanager create-secret \
    --name radialwebappauthcreds \
    --secret-string file://../credentials/radial_auth.json