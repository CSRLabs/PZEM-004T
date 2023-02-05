"""Device handler for CSRLabs PZEM-004T Ver 3 based on PTVO.info firmware"""

from zigpy.profiles import zha
from zigpy.quirks import CustomCluster, CustomDevice
from zhaquirks import Bus, LocalDataCluster
from zigpy.zcl.clusters.homeautomation import Diagnostic, ElectricalMeasurement
from zigpy.zcl.clusters.general import Basic, OnOffConfiguration, AnalogInput, MultistateValue, MultistateInput
from zigpy.zcl.clusters.measurement import TemperatureMeasurement
from zigpy.zcl.clusters.smartenergy import Metering

from homeassistant.components.zha.sensor import ElectricalMeasurement as EM

from zhaquirks.const import (
    DEVICE_TYPE,
    ENDPOINTS,
    INPUT_CLUSTERS,
    MODELS_INFO,
    OUTPUT_CLUSTERS,
    PROFILE_ID,
    SKIP_CONFIGURATION,
)

TEMPERATURE_REPORTED = "temperature_reported"
VOLTAGE_REPORTED = "voltage_reported"
CURRENT_REPORTED = "current_reported"
POWER_REPORTED = "power_reported"
FREQUENCY_REPORTED = "frequency_reported"
POWER_FACTOR_REPORTED = "power_factor_reported"
APPARENT_POWER_REPORTED = "apparent_power_reported"

CONSUMPTION_REPORTED = "consumption_reported"
INSTANTANEOUS_DEMAND = "instantaneous_demand"

PTVO_DEVICE = 0xfffe


def myformatter(self, value: int) -> int | float:
    """Return 'normalized' value."""
    multiplier = getattr(self._channel, f"{self._div_mul_prefix}_multiplier")
    divisor = getattr(self._channel, f"{self._div_mul_prefix}_divisor")
    value = float(value * multiplier) / divisor
    return round(value, self._decimals)

EM.formatter = myformatter


class PtvoAnalogInputCluster(CustomCluster, AnalogInput):

    cluster_id = AnalogInput.cluster_id

    def __init__(self, *args, **kwargs):
        """Init."""
        self._current_state = {}
        self._current_value = 0
        self._v_value = 0
        self._c_value = 0
        super().__init__(*args, **kwargs)

    def _update_attribute(self, attrid, value):
        super()._update_attribute(attrid, value)
        
        if value is not None:
        
            if attrid == 85:
                self._current_value = value
            
            if attrid == 28:
                if value == "C":
                    """Chip temperature value."""
                    t_value = self._current_value * 100
                    self.endpoint.device.temperature_bus.listener_event(TEMPERATURE_REPORTED, t_value)
                    
                if value == "V":
                    """Voltage value."""
                    self._v_value = self._current_value
                    self.endpoint.device.electrical_bus.listener_event(VOLTAGE_REPORTED, self._v_value)
                    
                if value == "A":
                    """Current value."""
                    self._c_value = self._current_value
                    self.endpoint.device.electrical_bus.listener_event(CURRENT_REPORTED, self._c_value)
                    """Apparent Power value"""
                    a_p_value = self._v_value * self._c_value
                    self.endpoint.device.electrical_bus.listener_event(APPARENT_POWER_REPORTED, a_p_value)
                    
                if value == "W":
                    """Power value."""
                    p_value = self._current_value
                    p_value1 = self._current_value / 1000
                    self.endpoint.device.electrical_bus.listener_event(POWER_REPORTED, p_value)
                    self.endpoint.device.consumption_bus.listener_event(INSTANTANEOUS_DEMAND, p_value1)
                    
                if value == "Hz":
                    """Frequency value."""
                    f_value = self._current_value
                    self.endpoint.device.electrical_bus.listener_event(FREQUENCY_REPORTED, f_value)
                    
                if value == "pf":
                    """Power Factor value."""
                    pf_value = self._current_value
                    self.endpoint.device.electrical_bus.listener_event(POWER_FACTOR_REPORTED, pf_value)
                    
                if value == "Wh":
                    """Energy value."""
                    e_value = self._current_value / 1000
                    self.endpoint.device.consumption_bus.listener_event(CONSUMPTION_REPORTED, e_value)


class TemperatureMeasurementCluster(LocalDataCluster, TemperatureMeasurement):

    cluster_id = TemperatureMeasurement.cluster_id
    MEASURED_VALUE_ID = 0x0000

    def __init__(self, *args, **kwargs):
        """Init."""
        super().__init__(*args, **kwargs)
        self.endpoint.device.temperature_bus.add_listener(self)

    def temperature_reported(self, value):
        """Temperature reported."""
        self._update_attribute(self.MEASURED_VALUE_ID, value)


class ElectricalMeasurementCluster(LocalDataCluster, ElectricalMeasurement):
    """Electrical measurement cluster."""

    cluster_id = ElectricalMeasurement.cluster_id
    POWER_ID = 0x050B
    VOLTAGE_ID = 0x0505
    CURRENT_ID = 0x0508
    FREQUENCY_ID = 0x0300
    POWER_FACTOR_ID = 0x0510
    APPARENT_POWER_ID = 0x050F

    def __init__(self, *args, **kwargs):
        """Init."""
        super().__init__(*args, **kwargs)
        self.endpoint.device.electrical_bus.add_listener(self)

    def power_reported(self, value):
        """Power reported."""
        self._update_attribute(self.POWER_ID, value)
        
    def voltage_reported(self, value):
        """Voltage reported."""
        self._update_attribute(self.VOLTAGE_ID, value)
        
    def current_reported(self, value):
        """Current reported."""
        self._update_attribute(self.CURRENT_ID, value)
        
    def frequency_reported(self, value):
        """Frequency reported."""
        self._update_attribute(self.FREQUENCY_ID, value)
        
    def power_factor_reported(self, value):
        """Power Factor reported."""
        self._update_attribute(self.POWER_FACTOR_ID, value)
        
    def apparent_power_reported(self, value):
        """Apparent Power reported"""
        self._update_attribute(self.APPARENT_POWER_ID, value)


class MeteringCluster(LocalDataCluster, Metering):
    """Metering cluster to receive reports that are sent to the basic cluster."""

    cluster_id = Metering.cluster_id
    CURRENT_SUMM_DELIVERED_ID = 0x0000
    INSTANTANEOUS_DEMAND_ID = 0x0400
    
    UNIT_OF_MEASUREMENT = 0x0300
    MULTIPLIER = 0x0301
    DIVISOR = 0x0302
    SUMMATION_FORMATTING = 0x0303
    METERING_DEVICE_TYPE = 0x0306

    _CONSTANT_ATTRIBUTES = {
        0x0300: 0,  # unit_of_measure: kWh
        0x0301: 1,  # multiplier
        0x0302: 1000,  # divisor
        0x0303: 0b0_0100_011,  # summation_formatting
        0x0306: 0,  # metering_device_type: electric
    }

    def __init__(self, *args, **kwargs):
        """Init."""
        super().__init__(*args, **kwargs)
        self.endpoint.device.consumption_bus.add_listener(self)

        # initialize constant attributes
        self._update_attribute(self.UNIT_OF_MEASUREMENT, 0)
        self._update_attribute(self.MULTIPLIER, 1)
        self._update_attribute(self.DIVISOR, 1000)
        self._update_attribute(self.SUMMATION_FORMATTING, 0b0_0100_011)
        self._update_attribute(self.METERING_DEVICE_TYPE, 0)

    def consumption_reported(self, value):
        """Consumption reported."""
        self._update_attribute(self.CURRENT_SUMM_DELIVERED_ID, round(value))
        
    def instantaneous_demand(self, value):
        """Instantaneous demand reported."""
        self._update_attribute(self.INSTANTANEOUS_DEMAND_ID, value)


class pzem004t(CustomDevice):
    """PZEM-004T Ver 3 based on PTVO firmware."""

    def __init__(self, *args, **kwargs):
        """Init device."""
        self.temperature_bus = Bus()
        self.electrical_bus = Bus()
        self.consumption_bus = Bus()
        
        super().__init__(*args, **kwargs)

    signature = {
        MODELS_INFO: [("CSRLabs", "pzem004t")],
        ENDPOINTS: {
            # <SimpleDescriptor endpoint=1 profile=260 device_type=65534
            # device_version=1
            # input_clusters=[0, 7, 20]
            # output_clusters=[0, 18]>
            1: {
                PROFILE_ID: zha.PROFILE_ID,
                DEVICE_TYPE: PTVO_DEVICE,
                INPUT_CLUSTERS: [
                    Basic.cluster_id,
                    OnOffConfiguration.cluster_id,
                    MultistateValue.cluster_id,
                ],
                OUTPUT_CLUSTERS: [
                    Basic.cluster_id,
                    MultistateInput.cluster_id,
                ],
            },
            # <SimpleDescriptor endpoint=1 profile=260 device_type=65534
            # device_version=1
            # input_clusters=[12, 20]
            # output_clusters=[]>
            2: {
                PROFILE_ID: zha.PROFILE_ID,
                DEVICE_TYPE: PTVO_DEVICE,
                INPUT_CLUSTERS: [
                    AnalogInput.cluster_id,
                    MultistateValue.cluster_id,
                ],
                OUTPUT_CLUSTERS: [],
            },
            # <SimpleDescriptor endpoint=1 profile=260 device_type=65534
            # device_version=1
            # input_clusters=[12]
            # output_clusters=[]>
            3: {
                PROFILE_ID: zha.PROFILE_ID,
                DEVICE_TYPE: PTVO_DEVICE,
                INPUT_CLUSTERS: [AnalogInput.cluster_id],
                OUTPUT_CLUSTERS: [],
            },
        },
    }

    replacement = {
        SKIP_CONFIGURATION: True,
        ENDPOINTS: {
           1: {
                PROFILE_ID: zha.PROFILE_ID,
                DEVICE_TYPE: PTVO_DEVICE,
                INPUT_CLUSTERS: [
                    Basic.cluster_id,
                    OnOffConfiguration.cluster_id,
                    MultistateValue.cluster_id,
                    TemperatureMeasurementCluster,
                    ElectricalMeasurementCluster,
                    MeteringCluster,
                ],
                OUTPUT_CLUSTERS: [Basic.cluster_id],
            },
            2: {
                PROFILE_ID: zha.PROFILE_ID,
                DEVICE_TYPE: zha.DeviceType.METER_INTERFACE,
                INPUT_CLUSTERS: [
                    PtvoAnalogInputCluster,
                    MultistateValue.cluster_id,
                ],
                OUTPUT_CLUSTERS: [],
            },
            3: {
                PROFILE_ID: zha.PROFILE_ID,
                DEVICE_TYPE: zha.DeviceType.METER_INTERFACE,
                INPUT_CLUSTERS: [PtvoAnalogInputCluster],
                OUTPUT_CLUSTERS: [],
            },
        },
    }