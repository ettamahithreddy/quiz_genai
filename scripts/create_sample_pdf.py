import os
import pymupdf

def create_sample_pdf():
    os.makedirs("sample_data", exist_ok=True)
    doc = pymupdf.open()

    # Page 1: Chapter 1 - Introduction to Machine Learning
    page1 = doc.new_page(width=595, height=842)
    text_p1 = """Chapter 1: Introduction to Machine Learning

Machine Learning is a subfield of artificial intelligence that focuses on building applications that learn from data and improve their accuracy over time without being explicitly programmed.

Core Categories of Machine Learning:
1. Supervised Learning: Learning with labeled datasets where inputs correspond to known outputs.
2. Unsupervised Learning: Discovering hidden patterns, structures, and groupings in unlabeled data.
3. Reinforcement Learning: Training agents to make sequences of decisions by receiving rewards or penalties.

Key Concepts:
- Features are individual measurable properties or characteristics of observed phenomena.
- Target or Label is the output variable to be predicted by the model.
- Training Data is the dataset used to train the algorithm.
- Overfitting occurs when a model learns noise and details from training data to the extent that it negatively impacts performance on new data."""
    page1.insert_textbox(pymupdf.Rect(50, 50, 545, 780), text_p1, fontsize=12)

    # Page 2: Chapter 2 - Supervised Learning in Detail
    page2 = doc.new_page(width=595, height=842)
    text_p2 = """Chapter 2: Supervised Learning in Detail

Supervised learning uses labeled training data to learn a mapping function from input variables to target variables.

Main Types of Supervised Learning:
1. Regression: Predicts continuous numerical values. Examples include Linear Regression, Ridge Regression, and Support Vector Regression.
2. Classification: Predicts discrete categorical labels. Examples include Logistic Regression, Decision Trees, Random Forests, Support Vector Machines (SVM), and Naive Bayes.

Algorithms:
- Linear Regression models the relationship between dependent and independent variables using a linear equation.
- Logistic Regression is a classification algorithm used to estimate the probability of binary outcomes using the sigmoid activation function.
- Decision Trees split datasets based on feature thresholds using metrics such as Gini Impurity and Information Gain (Entropy).
- Random Forest is an ensemble learning method that constructs multiple decision trees during training and outputs the mode or mean prediction.

Evaluation Metrics for Classification:
- Accuracy is the ratio of correct predictions to total predictions.
- Precision measures the proportion of positive identifications that were actually correct.
- Recall or Sensitivity measures the proportion of actual positives that were identified correctly.
- F1 Score is the harmonic mean of precision and recall."""
    page2.insert_textbox(pymupdf.Rect(50, 50, 545, 780), text_p2, fontsize=12)

    # Page 3: Chapter 3 - Unsupervised Learning & Clustering
    page3 = doc.new_page(width=595, height=842)
    text_p3 = """Chapter 3: Unsupervised Learning & Clustering

Unsupervised learning algorithms find natural groupings and patterns in datasets without human supervision or predefined target labels.

Major Tasks:
1. Clustering: Grouping similar data instances together.
   - K-Means Clustering partitions n observations into k clusters where each observation belongs to the cluster with the nearest mean centroid.
   - Hierarchical Clustering builds nested clusters in either agglomerative (bottom-up) or divisive (top-down) hierarchy.
   - DBSCAN (Density-Based Spatial Clustering of Applications with Noise) groups points that are closely packed together and marks outliers as noise.

2. Dimensionality Reduction: Reducing the number of random variables under consideration.
   - Principal Component Analysis (PCA) transforms features into linearly uncorrelated principal components that maximize variance.
   - t-SNE (t-Distributed Stochastic Neighbor Embedding) is a non-linear technique well suited for high-dimensional visualization."""
    page3.insert_textbox(pymupdf.Rect(50, 50, 545, 780), text_p3, fontsize=12)

    # Page 4: Chapter 4 - Python Programming & Loops
    page4 = doc.new_page(width=595, height=842)
    text_p4 = """Chapter 4: Python Programming & Iteration Fundamentals

Python provides control flow statements for iterative execution of code blocks.

Types of Loops in Python:
1. For Loop: Iterates over sequences such as lists, tuples, dictionaries, strings, or range objects.
   Example: for i in range(5): print(i)
2. While Loop: Executes a set of statements as long as a boolean condition remains True.
   Example: while count < 10: count += 1

Loop Control Statements:
- Break terminates the loop immediately and transfers execution to the statement following the loop.
- Continue skips the current iteration and advances execution to the next iteration of the loop.
- Pass is a null statement used as a placeholder when syntactic structure requires a statement but no action is needed.
- Else clause with loops: Python supports an optional else block attached to for/while loops that executes ONLY when the loop completes normally without encountering a break statement.

List Comprehensions:
A concise syntax for creating lists from existing iterables: [x**2 for x in range(10) if x % 2 == 0]."""
    page4.insert_textbox(pymupdf.Rect(50, 50, 545, 780), text_p4, fontsize=12)

    output_path = os.path.join("sample_data", "Machine_Learning_Notes.pdf")
    doc.save(output_path)
    doc.close()
    print(f"Sample PDF created successfully at: {output_path}")

if __name__ == "__main__":
    create_sample_pdf()
