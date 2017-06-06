# check_netapp
check NetApp via Python API

There are several Icinga Checks for Netapp that use SNMP.
While this is usually fine, SNMP queries often end with a Timeout.
Especially so, if SNMP is used to query Volumes or Aggregates.
The typical NetApp Storage has a lot of these.

This check uses the NetApp API instead.
That way is faster and won't timeout.

Before it can be used, some preliminary setup is requiered:

1) Download NetApp SDK avaible at http://mysupport.netapp.com/NOW/cgi-bin/software?product=NetApp+Manageability+SDK&platform=All+Platforms
2) Create a monitoring user with read-only access on NetApp system
3) add proper NetApp API access to this user


