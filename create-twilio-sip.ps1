twilio api:trunking:v1:trunks:create --friendly-name "Langoedge trunk" --domain-name "langoedge.pstn.twilio.com"

#Inbound
twilio api:trunking:v1:trunks:origination-urls:create --trunk-sid <twilio_trunk_sid> --friendly-name "LiveKit SIP URI" --sip-url "sip:6cg1atpjn12.sip.livekit.cloud" --weight 1 --priority 1 --enabled
lk sip dispatch create dispatch-rule.json
lk sip inbound create inbound-trunk.json
#Outbound
lk sip outbound create outbound-trunk.json

lk dispatch create --new-room --agent-name my-telephony-agent --metadata '{"phone_number": "+61402675430"}'