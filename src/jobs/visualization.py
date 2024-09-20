
import matplotlib.pyplot as plt
import pycountry
import pycountry_convert as pcc
from fuzzywuzzy import process
from pyspark.sql import SparkSession
from pyspark.sql.functions import udf
from pyspark.sql.types import StringType

# Start a Spark session
spark = SparkSession.builder.appName('Visa Data Processing').getOrCreate()

# Load the dataset
df = spark.read.csv('/content/visa_number_in_japan.csv', header=True, inferSchema=True)

# Standardize the column names
new_column_names = [col_name.replace(' ', '_').replace('/', '').replace('.', '').replace(',', '')
                    for col_name in df.columns]
df = df.toDF(*new_column_names)

# Drop any rows with all null columns
df = df.dropna(how='all')

# Select only relevant columns
df = df.select('year', 'country', 'number_of_issued_numerical')

# Function to correct country names using fuzzy matching
def correct_country_name(name, threshold=85):
    countries = [country.name for country in pycountry.countries]
    corrected_name, score = process.extractOne(name, countries)
    if score >= threshold:
        return corrected_name
    return name  # Return the original name if no match found

# Function to get continent name based on country name
def get_continent_name(country_name):
    try:
        country_code = pcc.country_name_to_country_alpha2(country_name, cn_name_format='default')
        continent_code = pcc.country_alpha2_to_continent_code(country_code)
        return pcc.convert_continent_code_to_continent_name(continent_code)
    except:
        return None

# Correct country names using a UDF
correct_country_name_udf = udf(correct_country_name, StringType())
df = df.withColumn('country', correct_country_name_udf(df['country']))

# Manual corrections for country names
country_corrections = {
    'Andra': 'Russia', 'Antigua Berbuda': 'Antigua and Barbuda', 'Barrane': 'Bahrain',
    'Brush': 'Bhutan', 'Komoro': 'Comoros', 'Benan': 'Benin', 'Kiribass': 'Kiribati',
    'Gaiana': 'Guyana', 'Court Jiboire': "Côte d'Ivoire", 'Lesot': 'Lesotho',
    'Macau travel certificate': 'Macao', 'Moldoba': 'Moldova', 'Naure': 'Nauru',
    'Nigail': 'Niger', 'Palao': 'Palau', 'St. Christopher Navis': 'Saint Kitts and Nevis',
    'Santa Principa': 'Sao Tome and Principe', 'Saechel': 'Seychelles', 'Slinum': 'Saint Helena',
    'Swaji Land': 'Eswatini', 'Torque menistan': 'Turkmenistan', 'Tsubaru': 'Zimbabwe',
    'Kosovo': 'Kosovo'
}

df = df.replace(country_corrections, subset='country')

# Get continent names using a UDF
continent_udf = udf(get_continent_name, StringType())
df = df.withColumn('continent', continent_udf(df['country']))

# Create a SQL temporary view for running SQL queries
df.createGlobalTempView('japan_visa_11')

# Query to get visa data by continent and year
df_cont = spark.sql("""
    SELECT year, continent, sum(number_of_issued_numerical) visa_issued
    FROM global_temp.japan_visa
    WHERE continent IS NOT NULL
    GROUP BY year, continent
""")

# Convert to Pandas DataFrame for plotting
df_cont = df_cont.toPandas()

# Plot visa issuance by continent
plt.figure(figsize=(10, 6))
for continent in df_cont['continent'].unique():
    data = df_cont[df_cont['continent'] == continent]
    plt.bar(data['year'], data['visa_issued'], label=continent)

plt.title("Number of Visas Issued in Japan (2006-2017)")
plt.xlabel('Year')
plt.ylabel('Number of Visas Issued')
plt.legend(title='Continent')
plt.grid(True, linestyle='--', alpha=0.7)
plt.tight_layout()
plt.savefig('output/visa_number_in_japan_continent_2006_2017.png')
plt.show()

# Query to get top 10 countries for visas issued in 2017
df_country = spark.sql("""
    SELECT country, sum(number_of_issued_numerical) visa_issued
    FROM global_temp.japan_visa
    WHERE country NOT IN ('total', 'others')
    AND country IS NOT NULL
    AND year = 2017
    GROUP BY country
    ORDER BY visa_issued DESC
    LIMIT 10
""")

# Convert to Pandas DataFrame for plotting
df_country = df_country.toPandas()

# Plot top 10 countries by visas issued in 2017
plt.figure(figsize=(10, 6))
plt.bar(df_country['country'], df_country['visa_issued'], color='skyblue')
plt.title("Top 10 Countries by Visa Issued in 2017")
plt.xlabel('Country')
plt.ylabel('Number of Visas Issued')
plt.xticks(rotation=45)
plt.tight_layout()
plt.savefig('output/visa_number_in_japan_by_country_2017.png')
plt.show()

# Save the cleaned data to CSV
df.write.csv("output/visa_number_in_japan_cleaned.csv", header=True, mode='overwrite')

# Stop the Spark session
spark.stop()

