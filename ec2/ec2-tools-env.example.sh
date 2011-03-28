# Set up the necessary environment for ec2 tools to work
# source this file into your current shell
#
# see: http://docs.amazonwebservices.com/AWSEC2/latest/UserGuide/

# JAVA
export JAVA_HOME=/System/Library/Frameworks/JavaVM.framework/Home

# EC2 home and path
export EC2_HOME=~/bin/ec2-api-tools-1.4.1.2
export PATH=$PATH:$EC2_HOME/bin

# EC2 access credentials
export EC2_PRIVATE_KEY=~/.aws/pk-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX.pem
export EC2_CERT=~/.aws/cert-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX.pem

# set the european endpoint
export EC2_URL=https://ec2.eu-west-1.amazonaws.com
