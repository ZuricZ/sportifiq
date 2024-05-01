# <az_ml_install>
az extension add -n ml -y
# </az_ml_install>

## For backward compatibility - running on old subscription
# <set_variables>
GROUP="test_boys"
LOCATION="westeurope"
WORKSPACE="ml-gregor"
# </set_variables>

# If RESOURCE_GROUP_NAME is empty, the az configure is pending.
RESOURCE_GROUP_NAME=${RESOURCE_GROUP_NAME:-}
if [[ -z "$RESOURCE_GROUP_NAME" ]]
then
    echo "No resource group name [RESOURCE_GROUP_NAME] specified, defaulting to ${GROUP}."
    # Installing extension temporarily assuming the run is on old subscription
    # without bootstrap script.

    # <az_configure_defaults>
    az configure --defaults group=$GROUP workspace=$WORKSPACE location=$LOCATION
    # </az_configure_defaults>
    echo "Default resource group set to $GROUP"
else
    echo "Workflows are using the new subscription."
fi

az extension add -n ml -y
az extension update -n ml
az extension list
