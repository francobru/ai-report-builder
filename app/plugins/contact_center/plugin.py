"""Contact Center plugin \u2014 Productividad del Contact Center.

Defines the complete data contract for the monthly Contact Center report
produced for Hospital Alem\u00e1n with data sourced from Tecnovoz.
"""

from __future__ import annotations

from pathlib import Path

from app.core.plugin_registry import (
    ChartDefinition,
    ColumnSpec,
    DataSchema,
    KPIDefinition,
    PromptConfig,
    ReportPlugin,
)


class ContactCenterPlugin(ReportPlugin):

    name = "contact_center"
    display_name = "Productividad del Contact Center"
    description = (
        "Reporte mensual de productividad del Contact Center: "
        "volumen de llamadas, nivel de atenci\u00f3n y tiempos operativos."
    )

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def get_schema(self) -> DataSchema:
        return DataSchema(
            columns=[
                ColumnSpec("NUMDAY", dtype="object", required=True, description="Fecha DD/MM/YYYY"),
                ColumnSpec("TRANSFER", dtype="float64", required=True, description="Llamadas atendidas"),
                ColumnSpec("NOTRANSFER", dtype="float64", required=True, description="Llamadas no atendidas"),
                ColumnSpec("TOTALCALLS", dtype="float64", required=True, description="Total llamadas recibidas"),
                ColumnSpec("PCTATT", dtype="float64", required=True, description="Nivel de atenci\u00f3n (%)"),
                ColumnSpec("AVGCONNWAIT", dtype="object", required=True, description="Demora promedio (HH:MM:SS)"),
                ColumnSpec("AVGABNWAIT", dtype="object", required=True, description="Abandono promedio (HH:MM:SS)"),
                ColumnSpec("AVGTALKTIME", dtype="object", required=True, description="Conversaci\u00f3n promedio (HH:MM:SS)"),
                ColumnSpec("SVCLEVEL", dtype="float64", required=False, description="Nivel de servicio (%)"),
                ColumnSpec("SLCALLS", dtype="float64", required=False, description="Llamadas dentro de SL"),
                ColumnSpec("LOGDATE", dtype="float64", required=True, description="Fecha YYYYMMDD"),
            ],
            separator=";",
            decimal=",",
            encoding="utf-8",
            date_column="LOGDATE",
            has_total_row=True,
        )

    # ------------------------------------------------------------------
    # KPIs
    # ------------------------------------------------------------------

    def get_kpis(self) -> list[KPIDefinition]:
        return [
            KPIDefinition(
                id="recibidas",
                label="Recibidas",
                source_column="TOTALCALLS",
                aggregation="sum",
                format_str="{:,.0f}",
                description="Total de llamadas recibidas en el per\u00edodo",
            ),
            KPIDefinition(
                id="atendidas",
                label="Atendidas",
                source_column="TRANSFER",
                aggregation="sum",
                format_str="{:,.0f}",
                description="Total de llamadas atendidas",
            ),
            KPIDefinition(
                id="promedio_recibidas",
                label="Prom. Recibidas",
                source_column="TOTALCALLS",
                aggregation="mean",
                format_str="{:,.0f}",
                description="Promedio diario de llamadas recibidas",
            ),
            KPIDefinition(
                id="promedio_atendidas",
                label="Prom. Atendidas",
                source_column="TRANSFER",
                aggregation="mean",
                format_str="{:,.0f}",
                description="Promedio diario de llamadas atendidas",
            ),
            KPIDefinition(
                id="nivel_atencion",
                label="Nivel de Atenci\u00f3n",
                unit="%",
                aggregation="custom",
                format_str="{:.2f}%",
                description="Atendidas / Recibidas \u00d7 100",
            ),
            KPIDefinition(
                id="tiempo_conversacion",
                label="Conversaci\u00f3n",
                unit="HH:MM:SS",
                source_column="AVGTALKTIME",
                aggregation="mean_time",
                format_str="{}",
                description="Tiempo promedio de conversaci\u00f3n",
            ),
            KPIDefinition(
                id="tiempo_demora",
                label="Demora",
                unit="HH:MM:SS",
                source_column="AVGCONNWAIT",
                aggregation="mean_time",
                format_str="{}",
                description="Tiempo promedio de espera antes de ser atendido",
            ),
            KPIDefinition(
                id="tiempo_abandono",
                label="Abandono",
                unit="HH:MM:SS",
                source_column="AVGABNWAIT",
                aggregation="mean_time",
                format_str="{}",
                description="Tiempo promedio antes de que el llamante abandone",
            ),
        ]

    # ------------------------------------------------------------------
    # Charts
    # ------------------------------------------------------------------

    def get_charts(self) -> list[ChartDefinition]:
        return [
            ChartDefinition(
                id="daily_distribution",
                chart_type="bar_line",
                title="Distribuci\u00f3n diaria \u2014 {campaign}",
                x_column="date",
                y_columns=["TOTALCALLS", "TRANSFER"],
                line_column="PCTATT",
                description="Barras recibidas/atendidas + l\u00ednea nivel de atenci\u00f3n por d\u00eda",
            ),
            ChartDefinition(
                id="weekday_distribution",
                chart_type="grouped_bar_line",
                title="Distribuci\u00f3n por d\u00eda de semana",
                description="Agregado por d\u00eda de semana (lun\u2013dom) con l\u00ednea NA",
            ),
            ChartDefinition(
                id="campaign_volume",
                chart_type="horizontal_bar",
                title="Distribuci\u00f3n por campa\u00f1a",
                description="Barras horizontales recibidas/atendidas por campa\u00f1a",
            ),
            ChartDefinition(
                id="campaign_share",
                chart_type="donut",
                title="Participaci\u00f3n por campa\u00f1a",
                description="Donut con % de participaci\u00f3n de cada campa\u00f1a",
            ),
            ChartDefinition(
                id="monthly_evolution",
                chart_type="grouped_bar_line",
                title="Evoluci\u00f3n mensual {year}",
                description="Tendencia mensual Ene\u2013Dic con barras y l\u00ednea NA",
            ),
            ChartDefinition(
                id="skill_volume_top10",
                chart_type="horizontal_bar",
                title="Top 10 habilidades por volumen de llamadas recibidas",
                description="Barras horizontales recibidas/atendidas top 10 habilidades",
            ),
            ChartDefinition(
                id="outbound_result",
                chart_type="vertical_bar",
                title="Distribuci\u00f3n por resultado",
                description="Llamadas salientes por resultado (Conectado, No llama, etc.)",
            ),
            ChartDefinition(
                id="outbound_daily",
                chart_type="vertical_bar",
                title="Distribuci\u00f3n diaria \u2014 Llamadas salientes",
                description="Volumen diario de llamadas salientes",
            ),
        ]

    # ------------------------------------------------------------------
    # Campaign \u2194 Skill mapping
    # ------------------------------------------------------------------

    def get_campaign_mapping(self) -> dict[str, list[str]]:
        """Map campaign names to the skill CSV file stems they contain.

        The stems are matched case-insensitively against the uploaded filenames.
        """
        return {
            "Turnos": [
                "Donacion",
                "0800_onco",
                "Osde_210",
                "TelePerfomance",
                "TelePerf_Cons",
                "TelePerf_PM_Cons",
                "Turno_Consulta",
                "Turnos_Estudios",
                "Turnos_PM_Consulta",
                "Turnos_PM_Estudios",
                "Gipfel_PM",
                "Gipfel_Cober",
            ],
            "Conmutador": [
                "Busqueda_Personas",
                "Sede_Caballito",
                "Camilleros",
                "Conmutador",
                "RechazoComm",
            ],
            "Plan M\u00e9dico": [
                "PM_Consultas",
                "0800_coca_cola",
            ],
            "Portal": [
                "Portal_Digital",
                "Portal_Paciente",
            ],
            "Agendas": [
                "Agendas_medicas",
            ],
            "Camp HA": [
                "Camp_HA",
            ],
        }

    # ------------------------------------------------------------------
    # AI prompts
    # ------------------------------------------------------------------

    def get_prompts(self) -> PromptConfig:
        return PromptConfig(
            executive_summary=(
                "Sos un analista de datos del Hospital Alem\u00e1n. "
                "Redact\u00e1 un resumen ejecutivo de m\u00e1ximo 4 oraciones sobre la "
                "productividad del Contact Center del mes de {period}. "
                "Basate exclusivamente en los siguientes KPIs:\n\n{kpi_summary}\n\n"
                "Mencion\u00e1 las variaciones m\u00e1s relevantes respecto al mes anterior. "
                "Us\u00e1 tono profesional y neutro. No inventes datos."
            ),
            conclusions=(
                "En base a los datos del Contact Center de {period}:\n\n"
                "{kpi_summary}\n\n"
                "Redact\u00e1 3 a 5 conclusiones breves y concretas. "
                "Si alg\u00fan indicador est\u00e1 por debajo del objetivo (NA < 85%), "
                "mencionalo expl\u00edcitamente. No inventes datos."
            ),
            recommendations=(
                "En base a las conclusiones del Contact Center de {period}:\n\n"
                "{conclusions}\n\n"
                "Propon\u00e9 3 a 5 recomendaciones accionables para mejorar "
                "los indicadores. S\u00e9 espec\u00edfico y pr\u00e1ctico."
            ),
            anomaly_detection=(
                "Analiz\u00e1 los siguientes datos diarios del Contact Center "
                "de {period} e identific\u00e1 cualquier anomal\u00eda, pico inusual, "
                "o patr\u00f3n fuera de lo normal:\n\n{daily_data}\n\n"
                "Si no hay anomal\u00edas, indicalo. No inventes datos."
            ),
        )

    # ------------------------------------------------------------------
    # Template
    # ------------------------------------------------------------------

    def get_template_path(self) -> Path | None:
        templates_dir = Path(__file__).parent / "templates"
        pptx = templates_dir / "template.pptx"
        if pptx.exists():
            return pptx
        return None


# Module-level instance for auto-registration
plugin_instance = ContactCenterPlugin()
